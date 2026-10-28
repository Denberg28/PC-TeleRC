"""Shared fleet release contract; importable without Qt or hardware libraries."""
FROZEN_CHECKS=frozenset('fleet_map_central no_camera_controls no_video_runtime initial_no_authority per_rover_controls map_labels identity_isolated live_position_update stale_position_retained stale_controls_disabled offline_map_decode offline_no_fake_gps offline_no_network isolated_plans selection_no_authority map_edit_offline logo close_cleans_sessions'.split())
FROZEN_CHECKS |= frozenset('resize_opaque_map route_file_controls_visible roster_add_remove idle_map_no_repaint compact_layout_no_horizontal_scroll'.split())
FROZEN_CHECKS |= frozenset('projection_round_trip drag_pan_continuity drag_no_route_edit click_location_correct manual_view_survives_telemetry drag_interrupt_no_edit'.split())
FROZEN_CHECKS |= frozenset('map_action_popup planned_home_return planned_hold_roundtrip waypoint_drag route_line_drag_insert route_gesture_rover_isolated route_actions_no_authority'.split())

FROZEN_CHECKS |= frozenset('draft_undo_redo draft_history_rover_isolated native_plan_roundtrip native_plan_editable draft_recovery_no_authority'.split())

FROZEN_CHECKS |= frozenset('popup_route_file_roundtrip legacy_menu_draft_recovery compact_arrival_hold invalid_gps_stays_stale'.split())

FROZEN_CHECKS |= frozenset('fc_load_control_visible fc_view_read_only_modeless fc_snapshot_no_draft_mutation fc_stale_result_ignored'.split())
FROZEN_CHECKS |= frozenset('compact_dark_theme rover_icon_resolutions theme_assets_decode optional_panels_no_authority'.split())
FROZEN_CHECKS |= frozenset('unreadable_draft_retained draft_recovery_copy recovery_no_authority base_preference_failure_consistent'.split())
