include $(TOPDIR)/rules.mk

PKG_NAME:=veci-v2-package-manager
PKG_VERSION:=0.1
PKG_RELEASE:=1

include $(INCLUDE_DIR)/package.mk

define Package/veci-v2-package-manager
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI v2 signed APK app manager (development)
  DEPENDS:=+rpcd +jsonfilter
endef

define Package/veci-v2-package-manager/description
  Manual, authenticated APK add-on management with strict board, release,
  signed repository, storage and protected dependency preflight.
endef

define Build/Compile
endef

define Package/veci-v2-package-manager/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./veci2-apk $(1)/usr/libexec/rpcd/veci.v2.pkg
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./veci2-apk-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-package-manager.json
endef

$(eval $(call BuildPackage,veci-v2-package-manager))
