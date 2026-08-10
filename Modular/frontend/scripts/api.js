
const API = {
    call: function(backend, action, params) {
        if (!backend) return Promise.reject(new Error('Backend not available'));
        var payload = Object.assign({ action: action }, params || {});
        return backend.request(JSON.stringify(payload)).then(function(res) {
            return JSON.parse(res);
        });
    },

    init: function(backend) {
        return API.call(backend, 'init');
    },

    getTodayData: function(backend) {
        return API.call(backend, 'get_today_data');
    },

    getHistoryData: function(backend) {
        return API.call(backend, 'get_history_data');
    },

    getProcesses: function(backend) {
        return API.call(backend, 'get_processes');
    },

    startTimer: function(backend, duration, course, type, queueId) {
        var params = { duration: duration, course: course, type: type };
        if (queueId) params.queue_id = queueId;
        return API.call(backend, 'start_timer', params);
    },

    pauseTimer: function(backend) {
        return API.call(backend, 'pause_timer');
    },

    resumeTimer: function(backend) {
        return API.call(backend, 'resume_timer');
    },

    stopTimer: function(backend) {
        return API.call(backend, 'stop_timer');
    },

    manageQueue: function(backend, sub, item) {
        var params = Object.assign({ sub: sub }, item || {});
        return API.call(backend, 'manage_queue', params);
    },

    saveSessionNote: function(backend, sessionId, note) {
        return API.call(backend, 'save_session_note', { session_id: sessionId, note: note });
    },

    playTimelapse: function(backend, path, duration, distractions, data) {
        return API.call(backend, 'play_timelapse', { path: path, duration: duration, distractions: distractions, data: data });
    },

    setVisionUI: function(backend, active) {
        return API.call(backend, 'set_vision_ui', { active: active });
    },

    libList: function(backend) {
        return API.call(backend, 'lib_list');
    },

    libOpen: function(backend, filename) {
        return API.call(backend, 'lib_open', { filename: filename });
    },

    libPage: function(backend, page, zoom) {
        return API.call(backend, 'lib_page', { page: page, zoom: zoom });
    },

    libAnnot: function(backend, page, rect, tool, text) {
        return API.call(backend, 'lib_annot', { page: page, rect: rect, tool: tool, text: text });
    },

    libOpenNative: function(backend, filename) {
        return API.call(backend, 'lib_open_native', { filename: filename });
    },

    manageGoal: function(backend, sub, data) {
        var params = Object.assign({ sub: sub }, data || {});
        return API.call(backend, 'manage_goal', params);
    },

    manageHabit: function(backend, sub, data) {
        var params = Object.assign({ sub: sub }, data || {});
        return API.call(backend, 'manage_habit', params);
    },

    manageQuiz: function(backend, sub, data) {
        var params = Object.assign({ sub: sub }, data || {});
        return API.call(backend, 'manage_quiz', params);
    },

    manageFlashcard: function(backend, sub, data) {
        var params = Object.assign({ sub: sub }, data || {});
        return API.call(backend, 'manage_flashcard', params);
    },

    manageNote: function(backend, sub, data) {
        var params = Object.assign({ sub: sub }, data || {});
        return API.call(backend, 'manage_note', params);
    },

    manageHealth: function(backend, sub, data) {
        var params = Object.assign({ sub: sub }, data || {});
        return API.call(backend, 'manage_health', params);
    },

    manageNutrition: function(backend, sub, data) {
        var params = Object.assign({ sub: sub }, data || {});
        return API.call(backend, 'manage_nutrition', params);
    },

    importBodyScan: function(backend) {
        return API.call(backend, 'import_body_scan');
    },

    saveBodyScan: function(backend, data) {
        return API.call(backend, 'save_body_scan', { data: data });
    },

    saveSettings: function(backend, data) {
        return API.call(backend, 'save_settings', { data: data });
    },

    resetData: function(backend) {
        return API.call(backend, 'reset_data');
    },

    openFileDialog: function(backend) {
        return API.call(backend, 'open_file_dialog');
    },

    openFolderDialog: function(backend) {
        return API.call(backend, 'open_folder_dialog');
    },

    checkCurrentDistractions: function(backend) {
        return API.call(backend, 'check_current_distractions');
    },

    setAppMonitoring: function(backend, enabled) {
        return API.call(backend, 'set_app_monitoring', { enabled: enabled });
    },

    setAutoBlock: function(backend, enabled) {
        return API.call(backend, 'set_auto_block', { enabled: enabled });
    },

    setAllowedApps: function(backend, apps) {
        return API.call(backend, 'set_allowed_apps', { apps: apps });
    },

    setBlockedApps: function(backend, apps) {
        return API.call(backend, 'set_blocked_apps', { apps: apps });
    },

    setQuietMode: function(backend, enabled) {
        return API.call(backend, 'set_quiet_mode', { enabled: enabled });
    },

    getSyncStatus: function(backend) {
        return API.call(backend, 'get_sync_status');
    },

    syncNow: function(backend) {
        return API.call(backend, 'sync_now');
    },

    forceSyncNow: function(backend) {
        return API.call(backend, 'force_sync_now');
    },

    hardCloneRemote: function(backend, targetDevice) {
        var params = {};
        if (targetDevice) params.target_device = targetDevice;
        return API.call(backend, 'hard_clone_remote', params);
    },

    forceResetAllData: function(backend) {
        return API.call(backend, 'force_reset_all_data');
    },

    mapFolder: function(backend, path) {
        return API.call(backend, 'map_folder', { path: path });
    },

    unmapFolder: function(backend, path) {
        return API.call(backend, 'unmap_folder', { path: path });
    },

    getMappedFolders: function(backend) {
        return API.call(backend, 'get_mapped_folders');
    },

    openNetworkFolder: function(backend, path) {
        return API.call(backend, 'open_network_folder', { path: path });
    }
};
