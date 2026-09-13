from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}")
    p.write_text(text.replace(old, new, 1))


pi = "just_audio_platform_interface/lib/just_audio_platform_interface.dart"
replace_once(
    pi,
    '''  /// Seeks to the given index and position.\n  Future<SeekResponse> seek(SeekRequest request) {\n    throw UnimplementedError("seek() has not been implemented.");\n  }\n''',
    '''  /// Seeks to the given index and position.\n  Future<SeekResponse> seek(SeekRequest request) {\n    throw UnimplementedError("seek() has not been implemented.");\n  }\n\n  /// Seeks and returns only backend-confirmed outcome information. The\n  /// compatibility fallback still performs the seek but cannot prove where the\n  /// backend actually landed.\n  Future<ConfirmedSeekResponse> seekConfirmed(ConfirmedSeekRequest request) async {\n    await seek(SeekRequest(position: request.position, index: request.index));\n    return ConfirmedSeekResponse(\n      status: SeekConfirmationStatusMessage.unsupported,\n    );\n  }\n''',
)
replace_once(
    pi,
    '''class SeekResponse {\n  static SeekResponse fromMap(Map<dynamic, dynamic> map) => SeekResponse();\n}\n''',
    '''class SeekResponse {\n  static SeekResponse fromMap(Map<dynamic, dynamic> map) => SeekResponse();\n}\n\n/// Backend-confirmed outcome of a seek request.\nenum SeekConfirmationStatusMessage {\n  reached,\n  superseded,\n  rejected,\n  failed,\n  unsupported,\n}\n\n/// Information communicated when requesting a backend-confirmed seek.\nclass ConfirmedSeekRequest {\n  final String attemptId;\n  final Duration? position;\n  final int? index;\n\n  ConfirmedSeekRequest({\n    required this.attemptId,\n    this.position,\n    this.index,\n  });\n\n  Map<dynamic, dynamic> toMap() => <dynamic, dynamic>{\n        'attemptId': attemptId,\n        'position': position?.inMicroseconds,\n        'index': index,\n      };\n}\n\n/// Information returned after a backend-confirmed seek request.\nclass ConfirmedSeekResponse {\n  final SeekConfirmationStatusMessage status;\n  final Duration? actualPosition;\n  final int? actualIndex;\n  final String? errorMessage;\n\n  ConfirmedSeekResponse({\n    required this.status,\n    this.actualPosition,\n    this.actualIndex,\n    this.errorMessage,\n  });\n\n  static ConfirmedSeekResponse fromMap(Map<dynamic, dynamic> map) {\n    final rawStatus = map['status'] as String?;\n    final status = SeekConfirmationStatusMessage.values.firstWhere(\n      (value) => value.name == rawStatus,\n      orElse: () => SeekConfirmationStatusMessage.failed,\n    );\n    final rawPosition = map['actualPosition'];\n    return ConfirmedSeekResponse(\n      status: status,\n      actualPosition:\n          rawPosition is int ? Duration(microseconds: rawPosition) : null,\n      actualIndex: map['actualIndex'] as int?,\n      errorMessage: map['errorMessage'] as String?,\n    );\n  }\n}\n''',
)

mc = "just_audio_platform_interface/lib/method_channel_just_audio.dart"
replace_once(
    mc,
    '''  @override\n  Future<SeekResponse> seek(SeekRequest request) async {\n    return SeekResponse.fromMap((await _channel\n        .invokeMethod<Map<dynamic, dynamic>>('seek', request.toMap()))!);\n  }\n''',
    '''  @override\n  Future<SeekResponse> seek(SeekRequest request) async {\n    return SeekResponse.fromMap((await _channel\n        .invokeMethod<Map<dynamic, dynamic>>('seek', request.toMap()))!);\n  }\n\n  @override\n  Future<ConfirmedSeekResponse> seekConfirmed(\n      ConfirmedSeekRequest request) async {\n    return ConfirmedSeekResponse.fromMap(\n        (await _channel.invokeMethod<Map<dynamic, dynamic>>(\n            'seekConfirmed', request.toMap()))!);\n  }\n''',
)

ja = "just_audio/lib/just_audio.dart"
marker = '''/// An audio player that plays a gapless playlist of [AudioSource]s.\n'''
addition = '''/// Result state for a backend-confirmed seek.\nenum SeekConfirmationStatus {\n  reached,\n  superseded,\n  rejected,\n  failed,\n  unsupported,\n}\n\n/// Result of a backend-confirmed seek.\nclass SeekConfirmationResult {\n  final SeekConfirmationStatus status;\n  final Duration? actualPosition;\n  final int? actualIndex;\n  final String? errorMessage;\n\n  const SeekConfirmationResult(\n    this.status, {\n    this.actualPosition,\n    this.actualIndex,\n    this.errorMessage,\n  });\n\n  bool get reached => status == SeekConfirmationStatus.reached;\n\n  factory SeekConfirmationResult._fromMessage(\n      ConfirmedSeekResponse response) {\n    final status = switch (response.status) {\n      SeekConfirmationStatusMessage.reached => SeekConfirmationStatus.reached,\n      SeekConfirmationStatusMessage.superseded =>\n        SeekConfirmationStatus.superseded,\n      SeekConfirmationStatusMessage.rejected => SeekConfirmationStatus.rejected,\n      SeekConfirmationStatusMessage.failed => SeekConfirmationStatus.failed,\n      SeekConfirmationStatusMessage.unsupported =>\n        SeekConfirmationStatus.unsupported,\n    };\n    return SeekConfirmationResult(\n      status,\n      actualPosition: response.actualPosition,\n      actualIndex: response.actualIndex,\n      errorMessage: response.errorMessage,\n    );\n  }\n}\n\n'''
p = Path(ja)
text = p.read_text()
if text.count(marker) != 1:
    raise SystemExit("just_audio.dart: audio player marker mismatch")
p.write_text(text.replace(marker, addition + marker, 1))

seek_marker = '''  /// Seeks to the next item, or does nothing if there is no next item.\n'''
confirmed_method = '''  /// Seeks while requiring the active backend to report where it actually\n  /// landed. This never treats the optimistic Dart position update as proof of\n  /// success. Backends that do not implement confirmation return\n  /// [SeekConfirmationStatus.unsupported].\n  Future<SeekConfirmationResult> seekConfirmed(\n    final Duration? position, {\n    int? index,\n  }) async {\n    if (_disposed) {\n      return const SeekConfirmationResult(\n        SeekConfirmationStatus.failed,\n        errorMessage: 'Player disposed',\n      );\n    }\n    _pluginLoadRequest?.resetInitialSeekValues();\n    if (processingState == ProcessingState.loading ||\n        processingState == ProcessingState.idle) {\n      return const SeekConfirmationResult(SeekConfirmationStatus.rejected);\n    }\n\n    try {\n      _seeking = true;\n      final prevPlaybackEvent = playbackEvent;\n      _playerEventSubject.add(playerEvent.copyWith(\n        playbackEvent: prevPlaybackEvent.copyWith(\n          updatePosition: position,\n          updateTime: DateTime.now(),\n        ),\n      ));\n      _positionDiscontinuitySubject.add(PositionDiscontinuity(\n        PositionDiscontinuityReason.seek,\n        prevPlaybackEvent,\n        playbackEvent,\n      ));\n      final response = await (await _platform).seekConfirmed(\n        ConfirmedSeekRequest(\n          attemptId: _uuid.v4(),\n          position: position,\n          index: index,\n        ),\n      );\n      final result = SeekConfirmationResult._fromMessage(response);\n      if (result.reached && result.actualPosition != null) {\n        _playerEventSubject.add(playerEvent.copyWith(\n          playbackEvent: playbackEvent.copyWith(\n            updatePosition: result.actualPosition,\n            updateTime: DateTime.now(),\n          ),\n        ));\n      }\n      if (playing && !_active) {\n        _setPlatformActive(true)?.catchError((dynamic e) async => null);\n      }\n      return result;\n    } on PlayerInterruptedException catch (error) {\n      return SeekConfirmationResult(\n        SeekConfirmationStatus.superseded,\n        errorMessage: error.message,\n      );\n    } catch (error) {\n      return SeekConfirmationResult(\n        SeekConfirmationStatus.failed,\n        errorMessage: error.toString(),\n      );\n    } finally {\n      _seeking = false;\n    }\n  }\n\n'''
p = Path(ja)
text = p.read_text()
if text.count(seek_marker) != 1:
    raise SystemExit("just_audio.dart: seek insertion marker mismatch")
p.write_text(text.replace(seek_marker, confirmed_method + seek_marker, 1))

android = "just_audio/android/src/main/java/com/ryanheise/just_audio/AudioPlayer.java"
replace_once(
    android,
    '''    private Result seekResult;\n''',
    '''    private Result seekResult;\n    private Result confirmedSeekResult;\n''',
)
replace_once(
    android,
    '''    private void advancePlaybackSourceEpoch() {\n        playbackSourceEpoch++;\n        playbackControlEpoch++;\n        completePlaybackStart("superseded", null);\n    }\n''',
    '''    private void advancePlaybackSourceEpoch() {\n        playbackSourceEpoch++;\n        playbackControlEpoch++;\n        completePlaybackStart("superseded", null);\n        completeConfirmedSeek("superseded", null, false);\n    }\n''',
)
replace_once(
    android,
    '''    private void advancePlaybackControlEpoch() {\n        playbackControlEpoch++;\n        completePlaybackStart("superseded", null);\n    }\n''',
    '''    private void advancePlaybackControlEpoch() {\n        playbackControlEpoch++;\n        completePlaybackStart("superseded", null);\n        completeConfirmedSeek("superseded", null, false);\n    }\n''',
)
replace_once(
    android,
    '''        case Player.DISCONTINUITY_REASON_AUTO_TRANSITION:\n        case Player.DISCONTINUITY_REASON_SEEK:\n            updateCurrentIndex();\n            break;\n''',
    '''        case Player.DISCONTINUITY_REASON_AUTO_TRANSITION:\n            updateCurrentIndex();\n            completeConfirmedSeek("superseded", null, false);\n            break;\n        case Player.DISCONTINUITY_REASON_SEEK:\n            updateCurrentIndex();\n            if (confirmedSeekResult != null) {\n                completeConfirmedSeek("reached", null, true);\n            }\n            break;\n''',
)
replace_once(
    android,
    '''        case Player.STATE_ENDED:\n            completePlaybackStart("rejected", null);\n''',
    '''        case Player.STATE_ENDED:\n            completePlaybackStart("rejected", null);\n            completeConfirmedSeek("rejected", null, false);\n''',
)
replace_once(
    android,
    '''            case "seek":\n                Long position = getLong(call.argument("position"));\n                Integer index = call.argument("index");\n                seek(position == null ? C.TIME_UNSET : position / 1000, index, result);\n                break;\n''',
    '''            case "seek":\n                Long position = getLong(call.argument("position"));\n                Integer index = call.argument("index");\n                seek(position == null ? C.TIME_UNSET : position / 1000, index, result);\n                break;\n            case "seekConfirmed":\n                Long confirmedPosition = getLong(call.argument("position"));\n                Integer confirmedIndex = call.argument("index");\n                seekConfirmed(\n                    confirmedPosition == null ? C.TIME_UNSET : confirmedPosition / 1000,\n                    confirmedIndex,\n                    result);\n                break;\n''',
)
replace_once(
    android,
    '''    public void seek(final long position, final Integer index, final Result result) {\n        advancePlaybackControlEpoch();\n''',
    '''    public void seekConfirmed(\n            final long position,\n            final Integer index,\n            final Result result) {\n        advancePlaybackControlEpoch();\n        if (position == C.TIME_UNSET ||\n                player == null ||\n                player.getMediaItemCount() == 0 ||\n                processingState == ProcessingState.idle ||\n                processingState == ProcessingState.loading) {\n            Map<String, Object> response = new HashMap<>();\n            response.put("status", "rejected");\n            result.success(response);\n            return;\n        }\n        abortSeek();\n        confirmedSeekResult = result;\n        seekPos = position;\n        try {\n            int windowIndex = index != null ? index : player.getCurrentMediaItemIndex();\n            if (windowIndex < 0 || windowIndex >= player.getMediaItemCount()) {\n                completeConfirmedSeek("rejected", null, false);\n                return;\n            }\n            player.seekTo(windowIndex, position);\n        } catch (RuntimeException e) {\n            completeConfirmedSeek("failed", e.getMessage(), false);\n        }\n    }\n\n    private void completeConfirmedSeek(\n            String status,\n            String errorMessage,\n            boolean includeActualPosition) {\n        Result result = confirmedSeekResult;\n        if (result == null) return;\n        confirmedSeekResult = null;\n        seekPos = null;\n        Map<String, Object> response = new HashMap<>();\n        response.put("status", status);\n        if (includeActualPosition && player != null) {\n            response.put("actualPosition", 1000L * player.getCurrentPosition());\n            response.put("actualIndex", player.getCurrentMediaItemIndex());\n        }\n        if (errorMessage != null) {\n            response.put("errorMessage", errorMessage);\n        }\n        result.success(response);\n    }\n\n    public void seek(final long position, final Integer index, final Result result) {\n        advancePlaybackControlEpoch();\n''',
)
replace_once(
    android,
    '''    @Override\n    public void onPlayerError(PlaybackException error) {\n''',
    '''    @Override\n    public void onPlayerError(PlaybackException error) {\n        completeConfirmedSeek("failed", error.getMessage(), false);\n''',
)

darwin = "just_audio/darwin/just_audio/Sources/just_audio/AudioPlayer.m"
replace_once(
    darwin,
    '''        } else if ([@"seek" isEqualToString:call.method]) {\n            CMTime position = request[@"position"] == (id)[NSNull null] ? kCMTimePositiveInfinity : CMTimeMake([request[@"position"] longLongValue], 1000000);\n            [self seek:position index:request[@"index"] completionHandler:^(BOOL finished) {\n                result(@{});\n            }];\n''',
    '''        } else if ([@"seek" isEqualToString:call.method]) {\n            CMTime position = request[@"position"] == (id)[NSNull null] ? kCMTimePositiveInfinity : CMTimeMake([request[@"position"] longLongValue], 1000000);\n            [self seek:position index:request[@"index"] completionHandler:^(BOOL finished) {\n                result(@{});\n            }];\n        } else if ([@"seekConfirmed" isEqualToString:call.method]) {\n            if (_processingState == psIdle || _processingState == psLoading || request[@"position"] == (id)[NSNull null]) {\n                result(@{@"status": @"rejected"});\n            } else {\n                CMTime position = CMTimeMake([request[@"position"] longLongValue], 1000000);\n                [self seek:position index:request[@"index"] completionHandler:^(BOOL finished) {\n                    if (!finished) {\n                        result(@{@"status": @"superseded"});\n                        return;\n                    }\n                    result(@{\n                        @"status": @"reached",\n                        @"actualPosition": @((long long)[self getCurrentPosition] * 1000LL),\n                        @"actualIndex": @(self->_index),\n                    });\n                }];\n            }\n''',
)

test = "just_audio/test/just_audio_test.dart"
replace_once(
    test,
    '''  String? lastPlaybackStartAttemptId;\n  int playCallCount = 0;\n''',
    '''  String? lastPlaybackStartAttemptId;\n  int playCallCount = 0;\n  SeekConfirmationStatusMessage confirmedSeekStatus =\n      SeekConfirmationStatusMessage.reached;\n  Duration? confirmedSeekActualPosition;\n  int? confirmedSeekActualIndex;\n  String? confirmedSeekErrorMessage;\n  int confirmedSeekCallCount = 0;\n''',
)
replace_once(
    test,
    '''  @override\n  Future<SeekResponse> seek(SeekRequest request) async {\n    _setPosition(request.position ?? Duration.zero);\n    _index = request.index ?? 0;\n    _broadcastPlaybackEvent();\n    return SeekResponse();\n  }\n''',
    '''  @override\n  Future<SeekResponse> seek(SeekRequest request) async {\n    _setPosition(request.position ?? Duration.zero);\n    _index = request.index ?? 0;\n    _broadcastPlaybackEvent();\n    return SeekResponse();\n  }\n\n  @override\n  Future<ConfirmedSeekResponse> seekConfirmed(\n      ConfirmedSeekRequest request) async {\n    confirmedSeekCallCount++;\n    final actualPosition =\n        confirmedSeekActualPosition ?? request.position ?? Duration.zero;\n    final actualIndex = confirmedSeekActualIndex ?? request.index ?? _index;\n    if (confirmedSeekStatus == SeekConfirmationStatusMessage.reached) {\n      _setPosition(actualPosition);\n      _index = actualIndex;\n      _broadcastPlaybackEvent();\n    }\n    return ConfirmedSeekResponse(\n      status: confirmedSeekStatus,\n      actualPosition: confirmedSeekStatus == SeekConfirmationStatusMessage.reached\n          ? actualPosition\n          : null,\n      actualIndex: confirmedSeekStatus == SeekConfirmationStatusMessage.reached\n          ? actualIndex\n          : null,\n      errorMessage: confirmedSeekErrorMessage,\n    );\n  }\n''',
)
test_marker = '''  test('speed', () async {\n'''
tests = '''  test('confirmed seek returns backend-reached position and index', () async {\n    final player = AudioPlayer();\n    await player.setAudioSources([\n      AudioSource.uri(Uri.parse('https://foo.foo/foo.mp3')),\n      AudioSource.uri(Uri.parse('https://bar.bar/bar.mp3')),\n    ]);\n    final platform = mock.mostRecentPlayer!\n      ..confirmedSeekActualPosition = const Duration(seconds: 3)\n      ..confirmedSeekActualIndex = 1;\n\n    final result = await player.seekConfirmed(\n      const Duration(seconds: 2),\n      index: 1,\n    );\n\n    expect(result.status, SeekConfirmationStatus.reached);\n    expect(result.actualPosition, const Duration(seconds: 3));\n    expect(result.actualIndex, 1);\n    expect(platform.confirmedSeekCallCount, 1);\n    await player.dispose();\n  });\n\n  test('confirmed seek rejects while loading without backend call', () async {\n    final player = AudioPlayer();\n    await player.setUrl('https://foo.foo/foo.mp3');\n    final platform = mock.mostRecentPlayer!;\n    platform.blockLoad();\n    final loadFuture = player.setUrl('https://bar.bar/bar.mp3');\n    await player.processingStateStream\n        .firstWhere((state) => state == ProcessingState.loading);\n\n    final result = await player.seekConfirmed(const Duration(seconds: 2));\n\n    expect(result.status, SeekConfirmationStatus.rejected);\n    expect(platform.confirmedSeekCallCount, 0);\n    platform.unblockLoad();\n    await loadFuture;\n    await player.dispose();\n  });\n\n  test('confirmed seek propagates superseded without claiming reach', () async {\n    final player = AudioPlayer();\n    await player.setUrl('https://foo.foo/foo.mp3');\n    final platform = mock.mostRecentPlayer!\n      ..confirmedSeekStatus = SeekConfirmationStatusMessage.superseded;\n\n    final result = await player.seekConfirmed(const Duration(seconds: 2));\n\n    expect(result.status, SeekConfirmationStatus.superseded);\n    expect(result.reached, isFalse);\n    expect(result.actualPosition, isNull);\n    expect(platform.confirmedSeekCallCount, 1);\n    await player.dispose();\n  });\n\n'''
p = Path(test)
text = p.read_text()
if text.count(test_marker) != 1:
    raise SystemExit("test insertion marker mismatch")
p.write_text(text.replace(test_marker, tests + test_marker, 1))
