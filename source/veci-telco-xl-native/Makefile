# Optional VeCI-only XL native read-only components; does not depend on LuCI.
# Does not enable login, schedule refresh, alter modem, or generate credentials.
# All native libraries are dynamically linked from the EXISTING firmware.
include $(TOPDIR)/rules.mk

PKG_NAME:=veci-telco-xl-native
PKG_VERSION:=0.3.6
PKG_RELEASE:=1
PKG_BUILD_DEPENDS:=mbedtls
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

define Package/veci-telco-xl-native
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI Indonesia XL native read-only quota client components
  DEPENDS:=+libmbedtls21 +jsonfilter
endef

define Package/veci-telco-xl-native/description
  Native XL components: AES/HMAC crypto, strict HTTPS quota-only
  transport and bounded DATA-only parser, plus owner-initiated
  CIAM OTP, isolated token staging and strict MSISDN identity check.
  Profile read-only transport is staged with exact-identity gate; no automatic polling, no operator
  credentials, no SMS reader, no payment commands and no daemon.
  No LuCI dependency or UI changes; authentication remains unverified until physical UAT.
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
		-DVECI_XL_PROFILE_VARIANT \
		-Os -Wall -Wextra -Werror -ffunction-sections -fdata-sections \
		-o $(PKG_BUILD_DIR)/veci-xl-profile-http \
		$(CURDIR)/../veci-telco-indonesia/veci-xl-quota-http.c \
		$(TARGET_LDFLAGS) -Wl,--gc-sections -lmbedtls -lmbedx509 -lmbedcrypto
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) \
		-Os -Wall -Wextra -Werror -ffunction-sections -fdata-sections \
		-o $(PKG_BUILD_DIR)/veci-xl-ciam \
		$(CURDIR)/../veci-telco-indonesia/veci-xl-ciam.c \
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
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/veci-xl-ciam $(1)/usr/libexec/veci-xl-ciam
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/veci-xl-profile-http $(1)/usr/libexec/veci-xl-profile-http
	$(INSTALL_BIN) $(CURDIR)/../veci-telco-indonesia/files/usr/libexec/veci-xl-token-stage $(1)/usr/libexec/veci-xl-token-stage
	$(INSTALL_BIN) $(CURDIR)/../veci-telco-indonesia/files/usr/libexec/veci-xl-profile-identity-check $(1)/usr/libexec/veci-xl-profile-identity-check
	$(INSTALL_BIN) $(CURDIR)/../veci-telco-indonesia/files/usr/libexec/veci-xl-profile-chain $(1)/usr/libexec/veci-xl-profile-chain
	$(INSTALL_BIN) $(CURDIR)/../veci-telco-indonesia/files/usr/libexec/veci-xl-session-activate $(1)/usr/libexec/veci-xl-session-activate
	$(INSTALL_BIN) $(CURDIR)/../veci-telco-indonesia/files/usr/libexec/veci-xl-quota-refresh $(1)/usr/libexec/veci-xl-quota-refresh
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) $(CURDIR)/files/usr/libexec/rpcd/veci.xl $(1)/usr/libexec/rpcd/veci.xl
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) $(CURDIR)/files/usr/share/rpcd/acl.d/veci-xl-owner.json $(1)/usr/share/rpcd/acl.d/veci-xl-owner.json
	$(INSTALL_DIR) $(1)/www/veci
	$(INSTALL_DATA) $(CURDIR)/files/www/veci/xl-account.html $(1)/www/veci/xl-account.html
	$(INSTALL_DATA) $(CURDIR)/files/www/veci/xl-account.js $(1)/www/veci/xl-account.js
	$(INSTALL_BIN) $(CURDIR)/../veci-telco-indonesia/files/usr/libexec/veci-xl-quota-chain $(1)/usr/libexec/veci-xl-quota-chain
endef

$(eval $(call BuildPackage,veci-telco-xl-native))
