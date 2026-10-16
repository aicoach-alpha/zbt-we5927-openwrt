include $(TOPDIR)/rules.mk

PKG_NAME:=veci-app-catalog-we5927
PKG_VERSION:=1
PKG_RELEASE:=1
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/veci-app-catalog-we5927
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI app catalog for ZBT-WE5927
  DEPENDS:=+veci
endef

define Package/veci-app-catalog-we5927/description
 Provides the firmware-profile app catalog consumed by the generic VeCI Apps page.
endef

define Build/Compile
endef

define Package/veci-app-catalog-we5927/install
	$(INSTALL_DIR) $(1)/usr/share/veci/apps
	$(INSTALL_DATA) ./files/usr/share/veci/apps/*.json $(1)/usr/share/veci/apps/
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/95-veci-app-feed-we5927 $(1)/etc/uci-defaults/95-veci-app-feed-we5927
endef

$(eval $(call BuildPackage,veci-app-catalog-we5927))
