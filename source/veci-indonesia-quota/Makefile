include $(TOPDIR)/rules.mk
PKG_NAME:=veci-indonesia-quota
PKG_VERSION:=1
PKG_RELEASE:=1
PKGARCH:=all
include $(INCLUDE_DIR)/package.mk

define Package/veci-indonesia-quota
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Indonesia read-only telco quota bridge
  DEPENDS:=+veci +rpcd +jsonfilter
endef

define Package/veci-indonesia-quota/description
  Low-resource read-only XL quota widget bridge. OTP and tokens remain on an
  external authenticated server; no heavy Python runtime on the router.
endef

define Build/Compile
endef

define Package/veci-indonesia-quota/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.indonesia $(1)/usr/libexec/rpcd/veci.indonesia
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) ./files/usr/sbin/veci-quota-import $(1)/usr/sbin/veci-quota-import
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/veci-indonesia.json $(1)/usr/share/rpcd/acl.d/veci-indonesia.json
endef

$(eval $(call BuildPackage,veci-indonesia-quota))
