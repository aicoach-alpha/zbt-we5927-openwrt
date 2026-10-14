# Optional native myXL quota crypto; intentionally NOT installed in existing VeCI.
# Uses mbedTLS shared crypto already used by OpenWrt (when available).
include $(TOPDIR)/rules.mk

PKG_NAME:=veci-telco-xl-native
PKG_VERSION:=0.2.0
PKG_RELEASE:=1
PKG_BUILD_DEPENDS:=mbedtls
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

define Package/veci-telco-xl-native
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Indonesia myXL quota-only native crypto primitives
  DEPENDS:=+veci-telco-indonesia +libmbedtls21
endef

define Package/veci-telco-xl-native/description
  Small C AES-256-CBC/HMAC-SHA512 module for local authenticated myXL
  read-only quota adapter. No carrier credentials or secret keys embedded,
  no OTP reader, no remote proxy, and no purchases. NOT full login yet.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) -D_DEFAULT_SOURCE \
		-Os -Wall -Wextra -Werror \
		-o $(PKG_BUILD_DIR)/veci-xl-crypto \
		$(CURDIR)/../veci-telco-indonesia/veci-xl-crypto.c \
		$(TARGET_LDFLAGS) -lmbedcrypto
endef

define Package/veci-telco-xl-native/install
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/veci-xl-crypto $(1)/usr/libexec/veci-xl-crypto
endef

$(eval $(call BuildPackage,veci-telco-xl-native))
