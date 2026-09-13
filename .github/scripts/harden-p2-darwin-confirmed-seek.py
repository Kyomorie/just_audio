from pathlib import Path

p = Path('just_audio/darwin/just_audio/Sources/just_audio/AudioPlayer.m')
text = p.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one match, found {count}')
    text = text.replace(old, new, 1)

replace_once(
'''    FlutterResult _playbackStartResult;
    long long _playbackSourceEpoch;
''',
'''    FlutterResult _playbackStartResult;
    FlutterResult _confirmedSeekResult;
    long long _confirmedSeekSourceEpoch;
    long long _confirmedSeekControlEpoch;
    int _confirmedSeekIndex;
    NSString *_confirmedSeekAttemptId;
    long long _playbackSourceEpoch;
''',
'confirmed seek ivars',
)

replace_once(
'''    _playbackStartResult = nil;
    _playbackSourceEpoch = 0;
''',
'''    _playbackStartResult = nil;
    _confirmedSeekResult = nil;
    _confirmedSeekSourceEpoch = 0;
    _confirmedSeekControlEpoch = 0;
    _confirmedSeekIndex = 0;
    _confirmedSeekAttemptId = nil;
    _playbackSourceEpoch = 0;
''',
'confirmed seek init',
)

replace_once(
'''        } else if ([@"seekConfirmed" isEqualToString:call.method]) {
            if (_processingState == psIdle || _processingState == psLoading || request[@"position"] == (id)[NSNull null]) {
                result(@{@"status": @"rejected"});
            } else {
                CMTime position = CMTimeMake([request[@"position"] longLongValue], 1000000);
                [self seek:position index:request[@"index"] completionHandler:^(BOOL finished) {
                    if (!finished) {
                        result(@{@"status": @"superseded"});
                        return;
                    }
                    result(@{
                        @"status": @"reached",
                        @"actualPosition": @((long long)[self getCurrentPosition] * 1000LL),
                        @"actualIndex": @(self->_index),
                    });
                }];
            }
''',
'''        } else if ([@"seekConfirmed" isEqualToString:call.method]) {
            CMTime position = request[@"position"] == (id)[NSNull null]
                ? kCMTimeInvalid
                : CMTimeMake([request[@"position"] longLongValue], 1000000);
            [self seekConfirmed:position
                          index:request[@"index"]
                      attemptId:(NSString *)request[@"attemptId"]
                         result:result];
''',
'handler confirmed seek',
)

replace_once(
'''- (void)advancePlaybackSourceEpoch {
    _playbackSourceEpoch++;
    _playbackControlEpoch++;
    [self completePlaybackStart:@"superseded" errorMessage:nil];
}

- (void)advancePlaybackControlEpoch {
    _playbackControlEpoch++;
    [self completePlaybackStart:@"superseded" errorMessage:nil];
}
''',
'''- (void)completeConfirmedSeek:(NSString *)status errorMessage:(NSString *)errorMessage includeActualPosition:(BOOL)includeActualPosition {
    if (!_confirmedSeekResult) return;
    FlutterResult result = _confirmedSeekResult;
    _confirmedSeekResult = nil;
    _confirmedSeekAttemptId = nil;
    NSMutableDictionary *response = [NSMutableDictionary dictionaryWithObject:status forKey:@"status"];
    if (includeActualPosition) {
        response[@"actualPosition"] = @((long long)[self getCurrentPosition] * 1000LL);
        response[@"actualIndex"] = @(_index);
    }
    if (errorMessage) {
        response[@"errorMessage"] = errorMessage;
    }
    result(response);
}

- (void)advancePlaybackSourceEpoch {
    _playbackSourceEpoch++;
    _playbackControlEpoch++;
    [self completePlaybackStart:@"superseded" errorMessage:nil];
    [self completeConfirmedSeek:@"superseded" errorMessage:nil includeActualPosition:NO];
}

- (void)advancePlaybackControlEpoch {
    _playbackControlEpoch++;
    [self completePlaybackStart:@"superseded" errorMessage:nil];
    [self completeConfirmedSeek:@"superseded" errorMessage:nil includeActualPosition:NO];
}
''',
'epoch completion',
)

replace_once(
'''- (void)complete {
    [self updatePosition];
    _processingState = psCompleted;
    [self evaluatePlaybackStart];
''',
'''- (void)complete {
    [self updatePosition];
    _processingState = psCompleted;
    [self completeConfirmedSeek:@"rejected" errorMessage:nil includeActualPosition:NO];
    [self evaluatePlaybackStart];
''',
'completion rejection',
)

replace_once(
'''- (void)sendError:(NSNumber *)errorCode errorMessage:(NSString *)errorMessage playerItem:(IndexedPlayerItem *)playerItem switchToIdle:(BOOL)switchToIdle {
    [self completePlaybackStart:@"failed" errorMessage:errorMessage];
''',
'''- (void)sendError:(NSNumber *)errorCode errorMessage:(NSString *)errorMessage playerItem:(IndexedPlayerItem *)playerItem switchToIdle:(BOOL)switchToIdle {
    [self completeConfirmedSeek:@"failed" errorMessage:errorMessage includeActualPosition:NO];
    [self completePlaybackStart:@"failed" errorMessage:errorMessage];
''',
'error completion',
)

replace_once(
'''- (void)seek:(CMTime)position index:(NSNumber *)newIndex completionHandler:(void (^)(BOOL))completionHandler {
    [self advancePlaybackControlEpoch];
    if (_processingState == psIdle || _processingState == psLoading) {
''',
'''- (void)seekConfirmed:(CMTime)position
                   index:(NSNumber *)newIndex
               attemptId:(NSString *)attemptId
                  result:(FlutterResult)result {
    if (_processingState == psIdle || _processingState == psLoading || !CMTIME_IS_VALID(position) || !_indexedAudioSources) {
        result(@{@"status": @"rejected"});
        return;
    }

    int targetIndex = _index;
    if (newIndex != (id)[NSNull null]) {
        targetIndex = [newIndex intValue];
    }
    if (targetIndex < 0 || targetIndex >= (int)_indexedAudioSources.count) {
        result(@{@"status": @"rejected"});
        return;
    }

    [self advancePlaybackControlEpoch];
    _confirmedSeekResult = result;
    _confirmedSeekSourceEpoch = _playbackSourceEpoch;
    _confirmedSeekControlEpoch = _playbackControlEpoch;
    _confirmedSeekIndex = targetIndex;
    _confirmedSeekAttemptId = [attemptId copy];
    NSString *capturedAttemptId = [_confirmedSeekAttemptId copy];

    [self seekInternal:position index:newIndex completionHandler:^(BOOL finished) {
        if (!self->_confirmedSeekResult || ![self->_confirmedSeekAttemptId isEqualToString:capturedAttemptId]) {
            return;
        }
        if (self->_confirmedSeekSourceEpoch != self->_playbackSourceEpoch
                || self->_confirmedSeekControlEpoch != self->_playbackControlEpoch
                || self->_confirmedSeekIndex != self->_index) {
            [self completeConfirmedSeek:@"superseded" errorMessage:nil includeActualPosition:NO];
            return;
        }
        if (!finished) {
            [self completeConfirmedSeek:@"superseded" errorMessage:nil includeActualPosition:NO];
            return;
        }
        [self completeConfirmedSeek:@"reached" errorMessage:nil includeActualPosition:YES];
    }];
}

- (void)seek:(CMTime)position index:(NSNumber *)newIndex completionHandler:(void (^)(BOOL))completionHandler {
    [self advancePlaybackControlEpoch];
    [self seekInternal:position index:newIndex completionHandler:completionHandler];
}

- (void)seekInternal:(CMTime)position index:(NSNumber *)newIndex completionHandler:(void (^)(BOOL))completionHandler {
    if (_processingState == psIdle || _processingState == psLoading) {
''',
'seek wrapper extraction',
)

p.write_text(text)
