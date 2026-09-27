let _pollInterval = null;

function startRealtimePoll(callback, intervalMs = 30000) {
    stopRealtimePoll();
    callback(); // immediate first call
    _pollInterval = setInterval(callback, intervalMs);
}

function stopRealtimePoll() {
    if (_pollInterval) {
        clearInterval(_pollInterval);
        _pollInterval = null;
    }
}
