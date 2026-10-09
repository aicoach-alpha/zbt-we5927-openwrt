include $(TOPDIR)/rules.mk

PKG_NAME:=veci-update-we5927
PKG_VERSION:=1
PKG_RELEASE:=1
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/veci-update-we5927
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI firmware update profile for ZBT-WE5927
  DEPENDS:=+veci +uclient-fetch
endef

define Package/veci-update-we5927/description
 Configures the VeCI firmware release channel and lightweight scheduled update checker for ZBT-WE5927.
endef

define Build/Compile
endef

define Package/veci-update-we5927/install
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/96-veci-update-we5927 $(1)/etc/uci-defaults/96-veci-update-we5927
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/veci-update-agent $(1)/etc/init.d/veci-update-agent
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) ./files/usr/sbin/veci-update-agent $(1)/usr/sbin/veci-update-agent
endef

define Package/veci-update-we5927/postinst
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] || {
	/etc/init.d/veci-update-agent enable >/dev/null 2>&1 || true
	/etc/init.d/veci-update-agent restart >/dev/null 2>&1 || true
}
endef

$(eval $(call BuildPackage,veci-update-we5927))
