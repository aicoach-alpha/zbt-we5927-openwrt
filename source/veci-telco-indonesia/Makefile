include $(TOPDIR)/rules.mk

PKG_NAME:=veci-telco-indonesia
PKG_VERSION:=0.2.2
PKG_RELEASE:=1
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/veci-telco-indonesia
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Indonesia operator quota status and registry
  DEPENDS:=+veci +rpcd +jsonfilter
endef

define Package/veci-telco-indonesia/description
 VeCI-only authenticated-carrier quota status contract and Indonesian
 operator registry. No LuCI pages, USSD, account secrets, or fake quota.
endef

define Build/Compile
endef

define Package/veci-telco-indonesia/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.quota $(1)/usr/libexec/rpcd/veci.quota
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) ./files/usr/libexec/veci-quota-cache $(1)/usr/libexec/veci-quota-cache
	$(INSTALL_DIR) $(1)/usr/share/veci/telco
	$(INSTALL_DATA) ./files/usr/share/veci/telco/providers.json $(1)/usr/share/veci/telco/providers.json
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/veci-quota.json $(1)/usr/share/rpcd/acl.d/veci-quota.json
endef

$(eval $(call BuildPackage,veci-telco-indonesia))
