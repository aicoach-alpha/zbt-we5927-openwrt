include $(TOPDIR)/rules.mk

PKG_NAME:=veci-app-guest
PKG_VERSION:=1
PKG_RELEASE:=1
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/veci-app-guest
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Guest Portal
  DEPENDS:=+veci +uspot +uspot-www
endef

define Package/veci-app-guest/description
 Installs the matched captive-portal runtime used by the VeCI guest application.
endef

define Build/Compile
endef

define Package/veci-app-guest/install
	$(INSTALL_DIR) $(1)/usr/share/veci/apps-installed
	touch $(1)/usr/share/veci/apps-installed/guest
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.app.guest $(1)/usr/libexec/rpcd/veci.app.guest
	$(INSTALL_DIR) $(1)/www/veci-apps
	$(INSTALL_DATA) ./files/www/veci-apps/guest.js $(1)/www/veci-apps/guest.js
endef

define Package/veci-app-guest/postinst
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] || {
	/etc/init.d/rpcd restart >/dev/null 2>&1 || true
}
endef

$(eval $(call BuildPackage,veci-app-guest))
