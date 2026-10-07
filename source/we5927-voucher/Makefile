include $(TOPDIR)/rules.mk

PKG_NAME:=we5927-voucher
PKG_RELEASE:=1

include $(INCLUDE_DIR)/package.mk

define Package/we5927-voucher
  SECTION:=net
  CATEGORY:=Network
  TITLE:=WE5927 lightweight guest voucher hotspot
  DEPENDS:=+opennds +luci-base +rpcd +uhttpd +jsonfilter
endef

define Package/we5927-voucher/description
 Lightweight guest captive portal integration for the WE5927 family.
 Uses openNDS for portal/session enforcement and a small project-owned
 voucher database for time-limited credentials.
endef

define Package/we5927-voucher/conffiles
/etc/config/we5927_voucher
endef

define Build/Compile
endef

define Package/we5927-voucher/install
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/we5927_voucher $(1)/etc/config/we5927_voucher
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/95-we5927-voucher $(1)/etc/uci-defaults/95-we5927-voucher
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) ./files/usr/sbin/we5927-voucher $(1)/usr/sbin/we5927-voucher
	$(INSTALL_DIR) $(1)/etc/we5927-voucher
endef

$(eval $(call BuildPackage,we5927-voucher))
