include $(TOPDIR)/rules.mk

PKG_NAME:=veci-v2-ui
PKG_VERSION:=0.1
PKG_RELEASE:=29

include $(INCLUDE_DIR)/package.mk

define Package/veci-v2-ui
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI v2 lightweight native UI (development preview)
  DEPENDS:=+veci-v2-runtime +veci-v2-package-manager +veci-v2-sms +veci-v2-ipv6 +uclient-fetch +ca-bundle +flock +uhttpd +uhttpd-mod-ubus +libustream-mbedtls +px5g-mbedtls
endef

define Package/veci-v2-ui/description
  Accessible zero-dependency SPA for exact-board health and signed packages.
  Not release-ready until all required LuCI/OEM/SMS/OTA modules pass UAT.
endef

define Build/Compile
endef

define Package/veci-v2-ui/install
	$(INSTALL_DIR) $(1)/www/cgi-bin
	$(INSTALL_BIN) ./files/www/cgi-bin/veci2-verify $(1)/www/cgi-bin/veci2-verify
	$(INSTALL_DATA) ./files/www/index.html $(1)/www/index.html
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/97-veci-v2-https $(1)/etc/uci-defaults/97-veci-v2-https
	$(INSTALL_DIR) $(1)/www/veci2
	$(INSTALL_DATA) ./files/www/veci2/index.html $(1)/www/veci2/index.html
	$(INSTALL_DATA) ./files/www/veci2/app.js $(1)/www/veci2/app.js
	$(INSTALL_DATA) ./files/www/veci2/sms-codec.js $(1)/www/veci2/sms-codec.js
	$(INSTALL_DATA) ./files/www/veci2/sms-center.js $(1)/www/veci2/sms-center.js
	$(INSTALL_DATA) ./files/www/veci2/speed-test.js $(1)/www/veci2/speed-test.js
	$(INSTALL_DATA) ./files/www/veci2/dns-settings.js $(1)/www/veci2/dns-settings.js
	$(INSTALL_DATA) ./files/www/veci2/owner-controls.js $(1)/www/veci2/owner-controls.js
	$(INSTALL_DATA) ./files/www/veci2/access.js $(1)/www/veci2/access.js
	$(INSTALL_DATA) ./files/www/veci2/routes.js $(1)/www/veci2/routes.js
	$(INSTALL_DATA) ./files/www/veci2/interfaces.js $(1)/www/veci2/interfaces.js
	$(INSTALL_DATA) ./files/www/veci2/ipv6-ra.js $(1)/www/veci2/ipv6-ra.js
	$(INSTALL_DATA) ./files/www/veci2/wifi-controls.js $(1)/www/veci2/wifi-controls.js
	$(INSTALL_DATA) ./files/www/veci2/cron.js $(1)/www/veci2/cron.js
	$(INSTALL_DATA) ./files/www/veci2/services.js $(1)/www/veci2/services.js
	$(INSTALL_BIN) ./files/www/cgi-bin/veci2-backup $(1)/www/cgi-bin/veci2-backup
	$(INSTALL_BIN) ./files/www/cgi-bin/veci2-restore $(1)/www/cgi-bin/veci2-restore
	$(INSTALL_DATA) ./files/www/veci2/backup.js $(1)/www/veci2/backup.js
	$(INSTALL_DATA) ./files/www/veci2/watchdog-status.js $(1)/www/veci2/watchdog-status.js
	$(INSTALL_DATA) ./files/www/veci2/observability.js $(1)/www/veci2/observability.js
	$(INSTALL_DATA) ./files/www/veci2/guest-check.js $(1)/www/veci2/guest-check.js
	$(INSTALL_DATA) ./files/www/veci2/update-policy.js $(1)/www/veci2/update-policy.js
	$(INSTALL_DATA) ./files/www/veci2/addon-profiles.js $(1)/www/veci2/addon-profiles.js
	$(INSTALL_DATA) ./files/www/veci2/monitor-settings.js $(1)/www/veci2/monitor-settings.js
	$(INSTALL_DATA) ./files/www/veci2/sim-lock.js $(1)/www/veci2/sim-lock.js
	$(INSTALL_DATA) ./files/www/veci2/app.css $(1)/www/veci2/app.css
	$(INSTALL_DATA) ./files/www/veci2/veci-design.css $(1)/www/veci2/veci-design.css
endef

$(eval $(call BuildPackage,veci-v2-ui))
