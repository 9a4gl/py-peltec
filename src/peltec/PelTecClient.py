# -*- coding: utf-8 -*-
"""
@author: Tihomir Heidelberg
"""

import logging

from peltec.PelTecHttpClient import PelTecHttpClient
from peltec.PelTecHttpHelper import PelTecHttpHelper
from peltec.PelTecWsClient import PelTecWsClient
from peltec.PelTecDeviceCollection import PelTecDeviceCollection

class PelTecClient:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.auto_reconnect = False
        self.websocket_connected = False
        self.ws_client = None
    
    def login(self, username, password):
        self.logger.info("PelTecClient - Logging in...")
        self.username = username
        self.password = password
        self.http_client = PelTecHttpClient(self.username, self.password)
        self.http_helper = PelTecHttpHelper(self.http_client)
        self.data = PelTecDeviceCollection()
        return self.http_client.login()

    def get_configuration(self):
        self.http_client.get_installations()
        if self.http_helper.get_device_count() == 0:
            self.logger.warning("PelTecClient - there is no installed device")
            return False
        self.http_client.get_configuration()
        self.http_client.get_widgetgrid_list()
        self.http_client.get_widgetgrid(self.http_client.widgetgrid_list["selected"])
        self.http_client.get_installation_status_all(self.http_helper.get_all_devices_ids())
        for serial in self.http_helper.get_all_devices_serials():
            self.http_client.get_parameter_list(serial)
        self.data.parse_installations(self.http_client.installations)
        self.data.parse_installation_statuses(self.http_client.installation_status_all)
        self.data.parse_parameter_lists(self.http_client.parameter_list)
        self.http_client.get_notifications()
        return True

    def close_websocket(self) -> bool:
        try:
            if self.ws_client is not None:
                self.ws_client.close()
                self.ws_client = None
            return True
        except Exception as e:
            self.logger.error("PelTecClient::close_websocket failed" + str(e))
            return False

    def start_websocket(self, on_parameter_updated_callback, auto_reconnect : bool = False):
        self.logger.info("PelTecClient - Starting...")
        self.close_websocket()
        self.ws_client = PelTecWsClient(self.ws_connected_callback, self.ws_disconnected_callback, self.ws_error_callback, self.ws_data_callback)
        self.on_parameter_updated_callback = on_parameter_updated_callback
        self.auto_reconnect = auto_reconnect
        self.ws_client.start()

    def refresh(self) -> bool:
        try:
            for id in self.http_helper.get_all_devices_ids():
                self.http_client.refresh_device(id)
                self.http_client.rstat_all_device(id)
            return True
        except Exception as e:
            self.logger.error("PelTecClient::refresh failed" + str(e))
            return False

    def ws_connected_callback(self, ws, frame):
        self.logger.info("PelTecClient - connected")
        self.websocket_connected = True
        self.ws_client.subscribe_to_notifications(ws)
        for serial in self.http_helper.get_all_devices_serials():
            self.ws_client.subscribe_to_installation(ws, serial)
        for device in self.data.values():
            parameters = device["parameters"]
            for parameter in parameters.values():
                self.on_parameter_updated_callback(device, parameter, True)
        self.data.set_on_update_callback(self.on_parameter_updated_callback)
        self.refresh()

    def ws_disconnected_callback(self, ws, close_status_code, close_msg):
        self.websocket_connected = False
        self.logger.warning(f"PelTecClient - disconnected close_status_code:{close_status_code} close_msg:{close_msg}")
        if self.auto_reconnect:
            self.logger.info("Webcocket reconnecting...")
            self.start(self.on_parameter_updated_callback)

    def ws_error_callback(self, ws, err):
        self.logger.error(f"PelTecClient - error err:{err}")
    
    def ws_data_callback(self, ws, stomp_frame):        
        self.data.parse_real_time_frame(stomp_frame)

    def stop(self):
        self.auto_reconnect = False
        if self.ws_client:
            self.ws_client.close()

    def is_websocket_connected(self) -> bool:
        return self.websocket_connected
