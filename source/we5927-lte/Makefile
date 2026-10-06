include $(TOPDIR)/rules.mk

PKG_NAME:=we5927-lte
PKG_RELEASE:=2

include $(INCLUDE_DIR)/package.mk

define Package/we5927-lte
  SECTION:=net
  CATEGORY:=Network
  TITLE:=ZBT WE5927 LTE / Dual-SIM manager
  DEPENDS:=+luci-base +rpcd +uhttpd +jsonfilter +kmod-usb-core +kmod-usb2 +kmod-usb-ohci +kmod-usb-net +kmod-usb-net-cdc-ether +kmod-usb-net-rndis +kmod-usb-serial +kmod-usb-serial-wwan +kmod-usb-serial-option
endef

define Package/we5927-lte/description
 LTE automation for ZBT WE5927 / WE2825-2SIM.
 CX07E 05c6:902e RNDIS, AT control, reconnect, modem power-cycle and dual-SIM failover.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) ./src/we5927-at.c $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) -o $(PKG_BUILD_DIR)/we5927-at $(PKG_BUILD_DIR)/we5927-at.c $(TARGET_LDFLAGS)
endef

define Package/we5927-lte/conffiles
/etc/config/we5927_lte
endef

define Package/we5927-lte/install
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/we5927-at $(1)/usr/sbin/we5927-at
	$(INSTALL_BIN) ./files/usr/sbin/we5927-lte $(1)/usr/sbin/we5927-lte
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/we5927-lte $(1)/etc/init.d/we5927-lte
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/we5927_lte $(1)/etc/config/we5927_lte
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/98-we5927-websafe $(1)/etc/uci-defaults/98-we5927-websafe
	$(INSTALL_BIN) ./files/etc/uci-defaults/99-we5927-lte $(1)/etc/uci-defaults/99-we5927-lte
	$(INSTALL_DIR) $(1)/etc/hotplug.d/usb
	$(INSTALL_BIN) ./files/etc/hotplug.d/usb/30-we5927-lte $(1)/etc/hotplug.d/usb/30-we5927-lte
	$(INSTALL_DIR) $(1)/www/luci-static/resources/view
	$(INSTALL_DATA) ./files/www/luci-static/resources/view/we5927_lte.js $(1)/www/luci-static/resources/view/we5927_lte.js
	$(INSTALL_DIR) $(1)/usr/share/luci/menu.d
	$(INSTALL_DATA) ./files/usr/share/luci/menu.d/luci-app-we5927-lte.json $(1)/usr/share/luci/menu.d/luci-app-we5927-lte.json
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/luci-app-we5927-lte.json $(1)/usr/share/rpcd/acl.d/luci-app-we5927-lte.json
endef

$(eval $(call BuildPackage,we5927-lte))
