include $(TOPDIR)/rules.mk

PKG_NAME:=veci-sms-we5927
PKG_VERSION:=1.6.0
PKG_RELEASE:=1
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

define Package/veci-sms-we5927
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI WE5927 SMS Inbox, Send, Sent, Drafts
  DEPENDS:=+veci +veci-cellular-we5927 +we5927-lte +rpcd +jsonfilter
endef

define Package/veci-sms-we5927/description
  User-initiated private SMS messages and drafts. Never polls modem.
  Preserves existing root-only SMS storage and consent state.
  No USSD or LuCI component.
endef

define Package/veci-sms-we5927/conffiles
/etc/veci-sms-feature
/etc/veci-sms-sent-history
/etc/veci-sms-drafts
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) \
		-Os -Wall -Wextra -Werror -o $(PKG_BUILD_DIR)/veci-sms-cmgs \
		$(CURDIR)/src/veci-sms-cmgs.c $(TARGET_LDFLAGS)
endef

define Package/veci-sms-we5927/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/veci.sms $(1)/usr/libexec/rpcd/veci.sms
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/veci-sms-cmgs $(1)/usr/libexec/veci-sms-cmgs
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-mifi-inbox $(1)/usr/libexec/veci-sms-mifi-inbox
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-inbox-index $(1)/usr/libexec/veci-sms-inbox-index
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-delete-one $(1)/usr/libexec/veci-sms-delete-one
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-send-one $(1)/usr/libexec/veci-sms-send-one
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-sent-history $(1)/usr/libexec/veci-sms-sent-history
	$(INSTALL_BIN) ./files/usr/libexec/veci-sms-drafts $(1)/usr/libexec/veci-sms-drafts
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json $(1)/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
	$(INSTALL_DIR) $(1)/www/veci
	$(INSTALL_DATA) ./files/www/veci/sms-center.css $(1)/www/veci/sms-center.css
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/95-veci-sms-files $(1)/etc/uci-defaults/95-veci-sms-files
endef

define Package/veci-sms-we5927/postinst
#!/bin/sh
[ -n "$\${IPKG_INSTROOT}" ] || {
	/etc/init.d/rpcd restart >/dev/null 2>&1 || true
}
endef

$(eval $(call BuildPackage,veci-sms-we5927))
