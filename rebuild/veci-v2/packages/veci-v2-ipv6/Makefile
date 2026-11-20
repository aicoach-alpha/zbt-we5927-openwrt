include $(TOPDIR)/rules.mk
PKG_NAME:=veci-v2-ipv6
PKG_VERSION:=0.1
PKG_RELEASE:=2
PKGARCH:=all
include $(INCLUDE_DIR)/package.mk
define Package/veci-v2-ipv6
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI v2 guarded IPv6 (off by default)
  DEPENDS:=+rpcd +jsonfilter +uci +flock
endef
# Shell/config-only package: do not invoke make in the empty build directory.
define Build/Compile
endef
define Package/veci-v2-ipv6/description
  Explicit IPv6 saved preference; only applies on admin-initiated reboot.
endef
define Package/veci-v2-ipv6/conffiles
/etc/config/veci2_ipv6
endef
define Package/veci-v2-ipv6/install
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/veci2_ipv6 $(1)/etc/config/veci2_ipv6
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/veci2-ipv6 $(1)/etc/init.d/veci2-ipv6
	$(INSTALL_DIR) $(1)/etc/rc.d
	$(LN) ../init.d/veci2-ipv6 $(1)/etc/rc.d/S16veci2-ipv6
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/90-veci2-ipv6-initial $(1)/etc/uci-defaults/90-veci2-ipv6-initial
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci2-ra $(1)/usr/libexec/rpcd/veci.v2.ra
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci2-ipv6 $(1)/usr/libexec/rpcd/veci.v2.ipv6
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/veci-v2-ipv6.json $(1)/usr/share/rpcd/acl.d/veci-v2-ipv6.json
endef
define Package/veci-v2-ipv6/postinst
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] || /etc/init.d/veci2-ipv6 enable >/dev/null 2>&1 || true
endef
$(eval $(call BuildPackage,veci-v2-ipv6))
