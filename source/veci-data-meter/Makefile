# Optional VeCI router data meter. No operator API access or LuCI dependency.
include $(TOPDIR)/rules.mk
PKG_NAME:=veci-data-meter
PKG_VERSION:=0.1.1
PKG_RELEASE:=1
include $(INCLUDE_DIR)/package.mk
define Package/veci-data-meter
 SECTION:=admin
 CATEGORY:=Administration
 TITLE:=VeCI LTE usage counters and optional manual quota estimate
 DEPENDS:=+jsonfilter +rpcd
endef
define Package/veci-data-meter/description
 Read actual usb0 LTE data usage. Optional user-supplied myXL remaining MB
 baseline is decremented by subsequent interface traffic. Never claim
 carrier authentication; estimate expires on modem reset or router reboot.
 No USSD, SMS, OTP, or private mobile application credentials.
endef
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef
define Build/Compile
endef
define Package/veci-data-meter/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) $(CURDIR)/files/usr/libexec/rpcd/veci.meter $(1)/usr/libexec/rpcd/veci.meter
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) $(CURDIR)/files/usr/share/rpcd/acl.d/veci-data-meter.json $(1)/usr/share/rpcd/acl.d/veci-data-meter.json
	$(INSTALL_DIR) $(1)/www/veci
	$(INSTALL_DATA) $(CURDIR)/files/www/veci/data-meter.html $(1)/www/veci/data-meter.html
	$(INSTALL_DATA) $(CURDIR)/files/www/veci/data-meter.js $(1)/www/veci/data-meter.js
endef
$(eval $(call BuildPackage,veci-data-meter))
