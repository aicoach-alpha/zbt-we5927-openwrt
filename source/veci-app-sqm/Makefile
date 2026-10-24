include $(TOPDIR)/rules.mk

PKG_NAME:=veci-app-sqm
PKG_VERSION:=1
PKG_RELEASE:=1
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/veci-app-sqm
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Smart Queue
  DEPENDS:=+veci +sqm-scripts +luci-app-sqm
endef

define Package/veci-app-sqm/description
 Installs SQM and its LuCI expert fallback from the exact VeCI firmware feed.
endef

define Build/Compile
endef

define Package/veci-app-sqm/install
	$(INSTALL_DIR) $(1)/usr/share/veci/apps-installed
	touch $(1)/usr/share/veci/apps-installed/sqm
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.app.sqm $(1)/usr/libexec/rpcd/veci.app.sqm
	$(INSTALL_DIR) $(1)/www/veci-apps
	$(INSTALL_DATA) ./files/www/veci-apps/sqm.js $(1)/www/veci-apps/sqm.js
endef

define Package/veci-app-sqm/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	/etc/init.d/rpcd restart >/dev/null 2>&1 || true
}
endef

define Package/veci-app-sqm/prerm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	ubus call veci.app.sqm cleanup '{}' >/dev/null 2>&1 || true
}
endef

$(eval $(call BuildPackage,veci-app-sqm))
