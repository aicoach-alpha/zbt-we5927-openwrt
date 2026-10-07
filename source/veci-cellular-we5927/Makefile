include $(TOPDIR)/rules.mk

PKG_NAME:=veci-cellular-we5927
PKG_RELEASE:=1

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

define Package/veci-cellular-we5927/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.cellular $(1)/usr/libexec/rpcd/veci.cellular
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/veci-cellular-we5927.json $(1)/usr/share/rpcd/acl.d/veci-cellular-we5927.json
endef

define Package/veci-cellular-we5927/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	/etc/init.d/rpcd restart >/dev/null 2>&1 || true
}
endef

$(eval $(call BuildPackage,veci-cellular-we5927))
