include $(TOPDIR)/rules.mk

PKG_NAME:=veci-app-ddns
PKG_VERSION:=1
PKG_RELEASE:=1
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/veci-app-ddns
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Dynamic DNS
  DEPENDS:=+veci +ddns-scripts +luci-app-ddns
endef

define Package/veci-app-ddns/description
 Installs Dynamic DNS and its LuCI expert fallback from the matched VeCI feed.
endef

define Build/Compile
endef

define Package/veci-app-ddns/install
	$(INSTALL_DIR) $(1)/usr/share/veci/apps-installed
	touch $(1)/usr/share/veci/apps-installed/ddns
endef

$(eval $(call BuildPackage,veci-app-ddns))
