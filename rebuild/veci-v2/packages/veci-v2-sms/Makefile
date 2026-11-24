include $(TOPDIR)/rules.mk

PKG_NAME:=veci-v2-sms
PKG_VERSION:=0.1
PKG_RELEASE:=1

include $(INCLUDE_DIR)/package.mk

define Package/veci-v2-sms
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI v2 SMS Center backend for ZBT-WE5927-DSIM
  DEPENDS:=+we5927-lte +rpcd +jsonfilter
  CONFLICTS:=veci-cellular-we5927
endef

define Package/veci-v2-sms/description
  Independent SMS Center backend: inbox, send, delete, sent and drafts.
  Reuses the single reviewed modem AT transport and port lock; no second
  modem daemon or AT polling, avoiding the known USB1.5 blocking risk.
endef

define Build/Compile
endef

define Package/veci-v2-sms/conffiles
/etc/config/veci_sms
/etc/veci-sms-sent-history
/etc/veci-sms-drafts
endef

define Package/veci-v2-sms/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd $(1)/usr/libexec
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.sms $(1)/usr/libexec/rpcd/veci.sms
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-parse $(1)/usr/libexec/veci-sms-parse
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-delete-one $(1)/usr/libexec/veci-sms-delete-one
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-send-one $(1)/usr/libexec/veci-sms-send-one
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-sent-history $(1)/usr/libexec/veci-sms-sent-history
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-drafts $(1)/usr/libexec/veci-sms-drafts
	$(INSTALL_DIR) $(1)/etc/config $(1)/etc/uci-defaults
	$(INSTALL_CONF) ./files/etc/config/veci_sms $(1)/etc/config/veci_sms
	$(INSTALL_BIN) ./files/etc/uci-defaults/97-veci-sms-userdata $(1)/etc/uci-defaults/97-veci-sms-userdata
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./veci-v2-sms-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-sms.json
endef

$(eval $(call BuildPackage,veci-v2-sms))
