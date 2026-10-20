# VeCI Native XL policy/RPC package: exact captured live source.
# Requires a separately installed Native XL executables package and overlay.
include $(TOPDIR)/rules.mk

PKG_NAME:=veci-xl-core-policy
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only
PKGARCH:=all
PKG_MAINTAINER:=VeCI contributors
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

define Package/veci-xl-core-policy
  SECTION:=net
  CATEGORY:=Network
  TITLE:=VeCI XL RPC and owner ACL policy from live router snapshot
  DEPENDS:=+veci-telco-xl-native +veci-xl-native-overlay +rpcd +jsonfilter
endef

define Package/veci-xl-core-policy/description
  Captured native XL account and quota dispatcher, owner ACL, and local logout
  helper. Contains no credentials and performs no OTP automatically.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/veci-xl-core-policy/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd $(1)/usr/share/rpcd/acl.d $(1)/usr/libexec
	$(INSTALL_BIN) ./files/veci.xl $(1)/usr/libexec/rpcd/veci.xl
	$(INSTALL_BIN) ./files/veci.quota $(1)/usr/libexec/rpcd/veci.quota
	$(INSTALL_DATA) ./files/veci-xl-owner.json $(1)/usr/share/rpcd/acl.d/veci-xl-owner.json
	$(INSTALL_BIN) ./files/veci-xl-session-clear $(1)/usr/libexec/veci-xl-session-clear
	chmod 0700 $(1)/usr/libexec/veci-xl-session-clear
endef

$(eval $(call BuildPackage,veci-xl-core-policy))
