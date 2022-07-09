/*
 * View model for OctoPrint-Smartabl
 *
 * Author: Paul Paukstelis
 * License: AGPLv3
 */
$(function() {
    function SmartablViewModel(parameters) {
        var self = this;

        // assign the injected parameters, e.g.:
        // self.loginStateViewModel = parameters[0];
        // self.settingsViewModel = parameters[1];

        // TODO: Implement your plugin's view model here.
    }

    // view model class, parameters for constructor, container to bind to
    OCTOPRINT_VIEWMODELS.push([
        SmartablViewModel,

        // e.g. loginStateViewModel, settingsViewModel, ...
        [ /* "loginStateViewModel", "settingsViewModel" */ ],

        // e.g. #settings_plugin_smartabl, #tab_plugin_smartabl, ...
        [ /* ... */ ]
    ]);
});
