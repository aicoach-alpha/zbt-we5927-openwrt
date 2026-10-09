include $(TOPDIR)/rules.mk

PKG_NAME:=veci-app-ddns
PKG_VERSION:=1
PKG_RELEASE:=1
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/veci-app-ddns
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Dynamic DNS
  DEPENDS:=+veci +ddns-scripts +luci-app-ddns +curl +ca-bundle
endef

define Package/veci-app-ddns/description
 Installs Dynamic DNS and its LuCI expert fallback from the matched VeCI feed.
endef

define Build/Compile
endef

define Package/veci-app-ddns/install
	$(INSTALL_DIR) $(1)/usr/share/veci/apps-installed
	touch $(1)/usr/share/veci/apps-installed/ddns
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.app.ddns $(1)/usr/libexec/rpcd/veci.app.ddns
	$(INSTALL_DIR) $(1)/www/veci-apps
	$(INSTALL_DATA) ./files/www/veci-apps/ddns.js $(1)/www/veci-apps/ddns.js
endef

define Package/veci-app-ddns/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	/etc/init.d/rpcd restart >/dev/null 2>&1 || true
}
endef

define Package/veci-app-ddns/prerm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	ubus call veci.app.ddns cleanup '{}' >/dev/null 2>&1 || true
}
endef

$(eval $(call BuildPackage,veci-app-ddns))
