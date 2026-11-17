include $(TOPDIR)/rules.mk

PKG_NAME:=veci-v2-ui
PKG_VERSION:=0.1
PKG_RELEASE:=1

include $(INCLUDE_DIR)/package.mk

define Package/veci-v2-ui
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI v2 lightweight native UI (development preview)
  DEPENDS:=+veci-v2-runtime +veci-v2-package-manager +veci-v2-sms +veci-v2-ipv6 +uhttpd +uhttpd-mod-ubus
endef

define Package/veci-v2-ui/description
  Accessible zero-dependency SPA for exact-board health and signed packages.
  Not release-ready until all required LuCI/OEM/SMS/OTA modules pass UAT.
endef

define Build/Compile
endef

define Package/veci-v2-ui/install
	$(INSTALL_DIR) $(1)/www/veci2
	$(INSTALL_DATA) ./files/www/veci2/index.html $(1)/www/veci2/index.html
	$(INSTALL_DATA) ./files/www/veci2/app.js $(1)/www/veci2/app.js
	$(INSTALL_DATA) ./files/www/veci2/sms-codec.js $(1)/www/veci2/sms-codec.js
	$(INSTALL_DATA) ./files/www/veci2/sms-center.js $(1)/www/veci2/sms-center.js
	$(INSTALL_DATA) ./files/www/veci2/app.css $(1)/www/veci2/app.css
endef

$(eval $(call BuildPackage,veci-v2-ui))
