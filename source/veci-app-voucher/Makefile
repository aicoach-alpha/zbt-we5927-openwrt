include $(TOPDIR)/rules.mk

PKG_NAME:=veci-app-voucher
PKG_VERSION:=1
PKG_RELEASE:=1
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/veci-app-voucher
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Voucher
  DEPENDS:=+veci +veci-app-guest +uspot
endef

define Package/veci-app-voucher/description
 Adds time-limited local guest vouchers on top of the VeCI guest captive portal.
endef

define Build/Compile
endef

define Package/veci-app-voucher/install
	$(INSTALL_DIR) $(1)/usr/share/veci/apps-installed
	touch $(1)/usr/share/veci/apps-installed/voucher
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.app.voucher $(1)/usr/libexec/rpcd/veci.app.voucher
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) ./files/usr/sbin/veci-voucher-cleaner $(1)/usr/sbin/veci-voucher-cleaner
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/veci-voucher-cleaner $(1)/etc/init.d/veci-voucher-cleaner
	$(INSTALL_DIR) $(1)/www/veci-apps
	$(INSTALL_DATA) ./files/www/veci-apps/voucher.js $(1)/www/veci-apps/voucher.js
endef

define Package/veci-app-voucher/postinst
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] || {
	/etc/init.d/rpcd restart >/dev/null 2>&1 || true
	/etc/init.d/veci-voucher-cleaner enable >/dev/null 2>&1 || true
	/etc/init.d/veci-voucher-cleaner restart >/dev/null 2>&1 || true
}
endef

define Package/veci-app-voucher/prerm
#!/bin/sh
[ -n "${IPKG_INSTROOT}" ] || {
	/etc/init.d/veci-voucher-cleaner stop >/dev/null 2>&1 || true
	/etc/init.d/veci-voucher-cleaner disable >/dev/null 2>&1 || true
}
endef

$(eval $(call BuildPackage,veci-app-voucher))
