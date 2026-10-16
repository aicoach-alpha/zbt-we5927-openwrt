include $(TOPDIR)/rules.mk

PKG_NAME:=veci-sms-inbox-we5927
PKG_VERSION:=0.1
PKG_RELEASE:=1

include $(INCLUDE_DIR)/package.mk

define Package/veci-sms-inbox-we5927
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=Opt-in admin-only SMS metadata index for WE5927
  DEPENDS:=+veci-cellular-we5927 +rpcd +jsonfilter +we5927-lte
endef

define Package/veci-sms-inbox-we5927/description
  Optional hardware-specific SMS metadata index, disabled unless installed
  separately. No message contents, sender or OTP are returned.
endef

define Build/Compile
endef

define Package/veci-sms-inbox-we5927/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.sms $(1)/usr/libexec/rpcd/veci.sms
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-inbox-index $(1)/usr/libexec/veci-sms-inbox-index
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json $(1)/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
endef

$(eval $(call BuildPackage,veci-sms-inbox-we5927))
