include $(TOPDIR)/rules.mk

PKG_NAME:=veci-ops-we5927
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKGARCH:=all
include $(INCLUDE_DIR)/package.mk

define Package/veci-ops-we5927
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI operator apps and firmware management RPC
  DEPENDS:=+veci +jsonfilter +rpcd +ca-bundle
endef

define Build/Compile
endef

define Package/veci-ops-we5927/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.apps $(1)/usr/libexec/rpcd/veci.apps
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/veci-ops.json $(1)/usr/share/rpcd/acl.d/veci-ops.json
endef

$(eval $(call BuildPackage,veci-ops-we5927))
