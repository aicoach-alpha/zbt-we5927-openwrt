# VeCI General cafe Apps manager (not a hotspot/Voucher server).
# Small whitelist-only UI backend. Must be built/signed for exact OpenWrt 25.12.
include $(TOPDIR)/rules.mk

PKG_NAME:=veci-general-apps
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only
PKGARCH:=all
PKG_MAINTAINER:=VeCI contributors
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

define Package/veci-general-apps
  SECTION:=net
  CATEGORY:=Network
  TITLE:=VeCI General: lightweight authenticated router Apps manager
  DEPENDS:=+rpcd +jsonfilter
endef

define Package/veci-general-apps/description
  Authenticated read/status and explicit write/install/uninstall RPC for
  allowlisted packages only; signed-feed, package-availability and overlay
  flash checks. Does not install voucher, bypass passwords or configure
  modem/firewall automatically.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/veci-general-apps/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd $(1)/usr/libexec $(1)/usr/share/rpcd/acl.d
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.apps $(1)/usr/libexec/rpcd/veci.apps
	$(INSTALL_BIN) ./files/usr/libexec/veci-general-app-worker $(1)/usr/libexec/veci-general-app-worker
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/veci-general-app-admin.json $(1)/usr/share/rpcd/acl.d/veci-general-app-admin.json
endef

$(eval $(call BuildPackage,veci-general-apps))
