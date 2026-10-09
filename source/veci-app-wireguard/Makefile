include $(TOPDIR)/rules.mk

PKG_NAME:=veci-app-wireguard
PKG_VERSION:=1
PKG_RELEASE:=1
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/veci-app-wireguard
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI WireGuard
  DEPENDS:=+veci +wireguard-tools +luci-proto-wireguard
endef

define Package/veci-app-wireguard/description
 Installs WireGuard tooling and LuCI protocol support from the exact VeCI firmware feed.
endef

define Build/Compile
endef

define Package/veci-app-wireguard/install
	$(INSTALL_DIR) $(1)/usr/share/veci/apps-installed
	touch $(1)/usr/share/veci/apps-installed/wireguard
endef

$(eval $(call BuildPackage,veci-app-wireguard))
