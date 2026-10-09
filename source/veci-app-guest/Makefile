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
endef

$(eval $(call BuildPackage,veci-app-guest))
