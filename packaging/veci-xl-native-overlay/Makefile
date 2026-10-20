# VeCI XL native addon: reproducible, no carrier credentials.
# Package is only an overlay for an existing compatible native XL RPC stack.
include $(TOPDIR)/rules.mk

PKG_NAME:=veci-xl-native-overlay
PKG_VERSION:=1.0.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only
PKG_MAINTAINER:=VeCI contributors
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

define Package/veci-xl-native-overlay
  SECTION:=net
  CATEGORY:=Network
  TITLE:=VeCI XL owner-login UI and local quota/session helpers
  DEPENDS:=+rpcd +jsonfilter
  PKGARCH:=all
endef

define Package/veci-xl-native-overlay/description
  Native VeCI XL account panel, authenticated quota cache gate, and
  offline authorized-configuration importer. Requires a pre-existing,
  separately installed veci-telco-xl-native RPC/ACL stack and Cellular UI
  mount. Does not ship API keys, customer tokens, modem controls or OTP.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/veci-xl-native-overlay/install
	$(INSTALL_DIR) $(1)/www/veci/js/lib $(1)/usr/libexec
	$(INSTALL_DATA) ./files/veci-xl-connection-status.js $(1)/www/veci/js/lib/veci-xl-connection-status.js
	$(INSTALL_BIN) ./files/veci-xl-quota-session-gate $(1)/usr/libexec/veci-xl-quota-session-gate
	$(INSTALL_BIN) ./files/veci-xl-authorized-config-import $(1)/usr/libexec/veci-xl-authorized-config-import
	chmod 0700 $(1)/usr/libexec/veci-xl-quota-session-gate $(1)/usr/libexec/veci-xl-authorized-config-import
endef

$(eval $(call BuildPackage,veci-xl-native-overlay))
