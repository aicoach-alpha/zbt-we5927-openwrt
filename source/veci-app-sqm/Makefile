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
endef

$(eval $(call BuildPackage,veci-app-sqm))
