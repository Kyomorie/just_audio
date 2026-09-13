from pathlib import Path

p = Path('just_audio/android/src/main/java/com/ryanheise/just_audio/AudioPlayer.java')
text = p.read_text()

old = '''        case Player.DISCONTINUITY_REASON_SEEK:
            updateCurrentIndex();
            if (confirmedSeekResult != null) {
                completeConfirmedSeek("reached", null, true);
            }
            break;
'''
new = '''        case Player.DISCONTINUITY_REASON_SEEK:
            updateCurrentIndex();
            if (confirmedSeekResult != null) {
                completeConfirmedSeekReached(newPosition);
            }
            break;
'''
if text.count(old) != 1:
    raise SystemExit('seek discontinuity block mismatch')
text = text.replace(old, new, 1)

replacements = {
    'completeConfirmedSeek("superseded", null, false);': 'completeConfirmedSeek("superseded", null);',
    'completeConfirmedSeek("rejected", null, false);': 'completeConfirmedSeek("rejected", null);',
    'completeConfirmedSeek("failed", error.getMessage(), false);': 'completeConfirmedSeek("failed", error.getMessage());',
    'completeConfirmedSeek("failed", e.getMessage(), false);': 'completeConfirmedSeek("failed", e.getMessage());',
}
for old_call, new_call in replacements.items():
    if old_call not in text:
        raise SystemExit(f'missing call: {old_call}')
    text = text.replace(old_call, new_call)

old_method = '''    private void completeConfirmedSeek(
            String status,
            String errorMessage,
            boolean includeActualPosition) {
        Result result = confirmedSeekResult;
        if (result == null) return;
        confirmedSeekResult = null;
        seekPos = null;
        Map<String, Object> response = new HashMap<>();
        response.put("status", status);
        if (includeActualPosition && player != null) {
            response.put("actualPosition", 1000L * player.getCurrentPosition());
            response.put("actualIndex", player.getCurrentMediaItemIndex());
        }
        if (errorMessage != null) {
            response.put("errorMessage", errorMessage);
        }
        result.success(response);
    }
'''
new_method = '''    private void completeConfirmedSeekReached(PositionInfo newPosition) {
        Result result = confirmedSeekResult;
        if (result == null) return;
        confirmedSeekResult = null;
        seekPos = null;
        result.success(mapOf(
            "status", "reached",
            "actualPosition", 1000L * newPosition.positionMs,
            "actualIndex", newPosition.mediaItemIndex
        ));
    }

    private void completeConfirmedSeek(String status, String errorMessage) {
        Result result = confirmedSeekResult;
        if (result == null) return;
        confirmedSeekResult = null;
        seekPos = null;
        Map<String, Object> response = new HashMap<>();
        response.put("status", status);
        if (errorMessage != null) {
            response.put("errorMessage", errorMessage);
        }
        result.success(response);
    }
'''
if text.count(old_method) != 1:
    raise SystemExit('confirmed seek completion helper mismatch')
text = text.replace(old_method, new_method, 1)

p.write_text(text)
