include $(TOPDIR)/rules.mk

PKG_NAME:=veci-cellular-we5927
PKG_RELEASE:=4

include $(INCLUDE_DIR)/package.mk

define Package/veci-cellular-we5927
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI cellular provider for WE5927
  DEPENDS:=+veci +we5927-lte +rpcd +jsonfilter
endef

define Package/veci-cellular-we5927/description
 Exposes the WE5927 LTE manager through the generic veci.cellular ubus contract.
endef

define Build/Compile
endef

define Package/veci-cellular-we5927/conffiles
/etc/config/veci_sms
/etc/veci-sms-sent-history
/etc/veci-sms-drafts
endef

define Package/veci-cellular-we5927/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.cellular $(1)/usr/libexec/rpcd/veci.cellular
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.sms $(1)/usr/libexec/rpcd/veci.sms
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) ./files/usr/libexec/veci-modem-capabilities $(1)/usr/libexec/veci-modem-capabilities
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-parse $(1)/usr/libexec/veci-sms-parse
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-delete-one $(1)/usr/libexec/veci-sms-delete-one
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-send-one $(1)/usr/libexec/veci-sms-send-one
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-drafts $(1)/usr/libexec/veci-sms-drafts
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-sent-history $(1)/usr/libexec/veci-sms-sent-history
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/veci_sms $(1)/etc/config/veci_sms
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/97-veci-sms-userdata $(1)/etc/uci-defaults/97-veci-sms-userdata
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/veci-cellular-we5927.json $(1)/usr/share/rpcd/acl.d/veci-cellular-we5927.json
endef

define Package/veci-cellular-we5927/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
    for data in /etc/veci-sms-drafts /etc/veci-sms-sent-history; do
        if [ ! -e "$$data" ]; then
            (umask 077; : > "$$data")
        fi
    done
	/etc/init.d/rpcd restart >/dev/null 2>&1 || true
}
endef

$(eval $(call BuildPackage,veci-cellular-we5927))
