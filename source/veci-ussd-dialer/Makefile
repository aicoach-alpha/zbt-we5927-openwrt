# Optional generic USSD dialer for VeCI only. Does not replace XL quota, LuCI, or Core.
include $(TOPDIR)/rules.mk
PKG_NAME:=veci-ussd-dialer
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
include $(INCLUDE_DIR)/package.mk

define Package/veci-ussd-dialer
 SECTION:=admin
 CATEGORY:=Administration
 TITLE:=VeCI interactive generic USSD dialer for WE5927
 DEPENDS:=+jsonfilter +rpcd
endef
define Package/veci-ussd-dialer/description
 User-initiated bounded USSD dial and manual menu choices for any active SIM.
 Standalone native VeCI interface. No USSD polling, quota parsing, XL credentials,
 voice-call ATD, SMS, SIM switching, LuCI changes or background automation.
endef
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef
define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) -std=c11 \
	  -Os -Wall -Wextra -Werror -ffunction-sections -fdata-sections \
	  -o $(PKG_BUILD_DIR)/veci-ussd-dialer-once \
	  $(CURDIR)/veci-ussd-once.c $(TARGET_LDFLAGS) -Wl,--gc-sections
endef
define Package/veci-ussd-dialer/install
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/veci-ussd-dialer-once $(1)/usr/libexec/veci-ussd-dialer-once
	$(INSTALL_BIN) $(CURDIR)/files/usr/libexec/veci-ussd-dialer $(1)/usr/libexec/veci-ussd-dialer
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) $(CURDIR)/files/usr/libexec/rpcd/veci.dialer $(1)/usr/libexec/rpcd/veci.dialer
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) $(CURDIR)/files/usr/share/rpcd/acl.d/veci-ussd-dialer.json $(1)/usr/share/rpcd/acl.d/veci-ussd-dialer.json
	$(INSTALL_DIR) $(1)/www/veci
	$(INSTALL_DATA) $(CURDIR)/files/www/veci/ussd-dialer.html $(1)/www/veci/ussd-dialer.html
	$(INSTALL_DATA) $(CURDIR)/files/www/veci/ussd-dialer.js $(1)/www/veci/ussd-dialer.js
endef
$(eval $(call BuildPackage,veci-ussd-dialer))
