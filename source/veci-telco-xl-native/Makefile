# Optional VeCI Indonesia XL native read-only quota components.
# Does not enable login, schedule refresh, alter modem, or generate credentials.
# All native libraries are dynamically linked from the EXISTING firmware.
include $(TOPDIR)/rules.mk

PKG_NAME:=veci-telco-xl-native
PKG_VERSION:=0.3.0
PKG_RELEASE:=1
PKG_BUILD_DEPENDS:=mbedtls
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

define Package/veci-telco-xl-native
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Indonesia XL native read-only quota client components
  DEPENDS:=+veci-telco-indonesia +libmbedtls21
endef

define Package/veci-telco-xl-native/description
  Three small native XL components: AES/HMAC crypto, strict HTTPS
  quota-only transport and bounded DATA-only parser, with staged
  protected local pipeline. No automatic login or polling, no operator
  credentials, no SMS reader, no payment commands and no daemon.
  THIS IS NOT AN AUTHENTICATED OPERATOR INTEGRATION UNTIL UAT.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) -D_DEFAULT_SOURCE \
		-Os -Wall -Wextra -Werror -ffunction-sections -fdata-sections \
		-o $(PKG_BUILD_DIR)/veci-xl-crypto \
		$(CURDIR)/../veci-telco-indonesia/veci-xl-crypto.c \
		$(TARGET_LDFLAGS) -Wl,--gc-sections -lmbedcrypto
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) \
		-Os -Wall -Wextra -Werror -ffunction-sections -fdata-sections \
		-o $(PKG_BUILD_DIR)/veci-xl-quota-http \
		$(CURDIR)/../veci-telco-indonesia/veci-xl-quota-http.c \
		$(TARGET_LDFLAGS) -Wl,--gc-sections -lmbedtls -lmbedx509 -lmbedcrypto
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) \
		-Os -Wall -Wextra -Werror -ffunction-sections -fdata-sections \
		-o $(PKG_BUILD_DIR)/veci-xl-quota-normalize \
		$(CURDIR)/../veci-telco-indonesia/veci-xl-quota-normalize.c \
		$(TARGET_LDFLAGS) -Wl,--gc-sections
endef

define Package/veci-telco-xl-native/install
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/veci-xl-crypto $(1)/usr/libexec/veci-xl-crypto
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/veci-xl-quota-http $(1)/usr/libexec/veci-xl-quota-http
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/veci-xl-quota-normalize $(1)/usr/libexec/veci-xl-quota-normalize
	$(INSTALL_BIN) $(CURDIR)/../veci-telco-indonesia/files/usr/libexec/veci-xl-quota-chain $(1)/usr/libexec/veci-xl-quota-chain
endef

$(eval $(call BuildPackage,veci-telco-xl-native))
