include $(TOPDIR)/rules.mk

PKG_NAME:=veci-wifi-guardian
PKG_RELEASE:=1

include $(INCLUDE_DIR)/package.mk

define Package/veci-wifi-guardian
  SECTION:=net
  CATEGORY:=Network
  TITLE:=VeCI MT7628 Wi-Fi service observer (no radio reload)
  DEPENDS:=+ubus +jsonfilter
endef

define Package/veci-wifi-guardian/description
 Read-only status monitor for WE5927 MT7628 radio and mt76 RX PSE counters.
 It never reloads, resets, or changes the Wi-Fi radio.
endef

define Build/Compile
endef

define Package/veci-wifi-guardian/install
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) ./veci-wifi-guardian $(1)/usr/sbin/veci-wifi-guardian
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/veci-wifi-guardian $(1)/etc/init.d/veci-wifi-guardian
endef

$(eval $(call BuildPackage,veci-wifi-guardian))
