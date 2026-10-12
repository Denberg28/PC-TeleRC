#!/usr/bin/env python3
"""Compare existing and optimized TeleRC direct-pair timing; not RF measurements.
Run: python3 bridge/simulation/simulate_direct.py --output /path/to/results
Requires numpy and matplotlib. Does not alter firmware or operate hardware.
"""
from pathlib import Path
import argparse, csv, json, math, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def airtime_ms(length):
    symbols=8+math.ceil((8*length-28+28+16)/28)*5
    return (8+4.25+symbols)*128/500000*1000

def rows_to_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def deadline_probability(packet_loss,cycle,duration):
    # Exact independent-loss reference for fixed refresh opportunities.
    # k prior failed exchanges cause timeout before the next opportunity.
    q=1-(1-packet_loss)**2
    states=math.ceil(500/cycle)
    alive=np.zeros(states);alive[0]=1
    opportunities=math.floor(duration/cycle)
    for _ in range(opportunities):
        alive[-1]=0 # this prior loss streak expires before this opportunity
        nxt=np.zeros(states);nxt[0]=alive.sum()*(1-q)
        if states>1:nxt[1:]=alive[:-1]*q
        alive=nxt
    remainder=duration-opportunities*cycle
    alive[np.arange(states)*cycle+remainder>=500]=0
    return 1-alive.sum()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    seed=20261011;events=500000;trials=100000
    rng=np.random.default_rng(seed)
    # Read the timing values from this repository's real firmware, rather than
    # silently allowing the simulation to drift from the implementation.
    core=(Path(__file__).resolve().parents[1]/'TeleRCMesh/MeshCore.h').read_text()
    match=re.search(r'legs==1\?Timing\{(\d+),(\d+)\}:Timing\{(\d+),(\d+)\}',core)
    if not match:raise RuntimeError('Cannot locate firmware timing profiles')
    direct_wait,direct_window,relay_wait,relay_window=map(int,match.groups())
    assert direct_wait>direct_window and relay_wait>relay_window
    assert re.search(r'AXIS_MS=500',core)
    assert abs(airtime_ms(57)-26.944)<1e-9
    assert abs(airtime_ms(67)-30.784)<1e-9

    host_tick=rng.uniform(0,50,events);wifi=rng.uniform(2,10,events)
    phase=rng.random(events);cad_poll=rng.uniform(1,3,events)
    cad_response=rng.uniform(1,3,events);processing=rng.uniform(.5,1.5,events)
    hb_phase=rng.random(events)
    results=[];distributions={};loss_rows=[];trace=[]
    profiles=[('Before',370,350),('Optimized direct',direct_wait,direct_window)]
    for profile,wait,window in profiles:
        cycles=wait+airtime_ms(57)+cad_poll
        cycle=float(cycles.mean())
        # One GCS heartbeat per second: bundling likelihood changes with poll rate.
        hb_chance=min(cycle/1000,1)
        response_air=np.where(hb_phase<hb_chance,airtime_ms(85),airtime_ms(67))
        rf_return=3+cad_response+processing+response_air
        assert np.all(rf_return<window)
        delay=host_tick+wifi+phase*cycles+rf_return+26*10/115200*1000
        distributions[profile]=delay
        results.append(dict(profile=profile,poll_wait_ms=wait,response_window_ms=window,
            mean_cycle_ms=cycle,update_hz=1000/cycle,mean_delay_ms=float(delay.mean()),
            p95_delay_ms=float(np.percentile(delay,95)),p99_delay_ms=float(np.percentile(delay,99)),
            modeled_rf_occupancy_pct=float((airtime_ms(57)+response_air.mean())/cycle*100),
            max_packet_cycle_ms=wait+airtime_ms(136)+3))
        # Constant representative cycle isolates loss behavior. Both legs have
        # independent packet loss; no stale retries and no auto recovery.
        for packet_loss in [0,.001,.005,.01,.05,.10]:
            first_stop=np.full(trials,np.inf);last=np.zeros(trials);latched=np.zeros(trials,bool)
            opportunities=math.floor(60000/cycle)
            for i in range(1,opportunities+1):
                now=i*cycle
                good=(rng.random(trials)>=packet_loss)&(rng.random(trials)>=packet_loss)
                expires=(now-last>=500)&~latched
                first_stop[expires]=last[expires]+500;latched|=expires
                last[good&~latched]=now
            expires=(60000-last>=500)&~latched
            first_stop[expires]=last[expires]+500;latched|=expires
            loss_rows.append(dict(profile=profile,loss_per_packet_pct=100*packet_loss,
                stopped_within_60s_pct=float(latched.mean()*100),
                exact_reference_stop_pct=100*deadline_probability(packet_loss,cycle,60000),
                trials=trials,exchanges=opportunities))
            expected=loss_rows[-1]['exact_reference_stop_pct']/100
            measured=loss_rows[-1]['stopped_within_60s_pct']/100
            # Independent analytical reference catches changes to the timing
            # model; allow Monte Carlo sampling variation, including rare events.
            assert abs(measured-expected)<=6*math.sqrt(expected*(1-expected)/trials)+6/trials
        # Same sequence in both profiles: two losses followed by fresh RC, then
        # three losses. Deadline expiry latches; nonneutral recovery is rejected.
        last=0;latched=False
        for i,good in enumerate([True,True,False,False,True,False,False,False,True],1):
            now=i*cycle
            if not latched and now-last>=500:
                trace.append(dict(profile=profile,time_ms=round(last+500,3),event='watchdog stop',latched=True))
                latched=True
            accepted=good and not latched
            if accepted:last=now
            trace.append(dict(profile=profile,time_ms=round(now,3),event='RC accepted' if accepted
                else 'nonneutral rejected after stop' if good else 'exchange lost',latched=latched))
    rows_to_csv(out/'timing_comparison.csv',results)
    rows_to_csv(out/'loss_comparison.csv',loss_rows)
    rows_to_csv(out/'fault_trace.csv',trace)
    rows_to_csv(out/'airtime.csv',[dict(bytes=n,airtime_ms=airtime_ms(n)) for n in [40,57,67,79,85,127,136]])

    # Preserve the previous range assumptions: no invented RX gain improvement.
    freq=915;threshold=-114;fspl=20*math.log10(4*math.pi*freq*1e6/299792458)
    range_rows=[]
    for environment,n,extra in [('Open, good antenna clearance',2.5,0),
            ('Low antennas / vegetation',3,6),('Built-up / obstructions',3.5,12)]:
        for power in [2,10,17]:
            distance=10**((power+2-threshold-10-fspl-extra)/(10*n))
            range_rows.append(dict(environment=environment,tx_dbm=power,range_with_10db_reserve_m=distance,
                path_loss_exponent=n,extra_loss_db=extra))
    rows_to_csv(out/'range_scenarios.csv',range_rows)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
    for profile,color in [('Before','#999999'),('Optimized direct','#267bad')]:
        ax[0].hist(distributions[profile],bins=75,density=True,alpha=.65,label=profile,color=color)
    ax[0].set(xlabel='Operator input → rover UART (ms)',ylabel='Probability density',title='Clear-channel input delay')
    ax[0].legend()
    levels=[0,.1,.5,1,5,10];x=np.arange(len(levels))
    for j,(profile,color) in enumerate([('Before','#999999'),('Optimized direct','#267bad')]):
        values=[r['stopped_within_60s_pct'] for r in loss_rows if r['profile']==profile]
        ax[1].bar(x+(j-.5)*.36,values,width=.36,label=profile,color=color)
    ax[1].set(xticks=x,xticklabels=[str(p) for p in levels],xlabel='Independent loss per packet (%)',
              ylabel='Sessions with a watchdog stop (%)',title='500 ms timeout · 60 s driving',ylim=(0,105))
    ax[1].legend()
    fig.suptitle('Two T3-S3 SX1262 boards · simulated optimization, not field measurements',fontsize=13)
    fig.savefig(out/'comparison.png',dpi=150);plt.close(fig)
    summary=dict(seed=seed,input_events=events,trials_per_loss_setting=trials,timing=results,
        loss=loss_rows,range=range_rows,relay_timing=dict(poll_ms=relay_wait,response_ms=relay_window),
        assumptions=dict(frequency_mhz=freq,rx_threshold_dbm=threshold,antenna_gain_each_dbi=2,
                         combined_losses_db=2,range_reserve_db=10))
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(dict(timing=results,loss=loss_rows),indent=2))

if __name__=='__main__':main()
