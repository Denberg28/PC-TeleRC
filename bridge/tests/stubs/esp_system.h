#pragma once
inline unsigned testRandom=42;
inline unsigned esp_random(){return ++testRandom;}
