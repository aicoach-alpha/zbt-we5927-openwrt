include $(TOPDIR)/rules.mk

PKG_NAME:=veci-v2-runtime
PKG_VERSION:=0.1
PKG_RELEASE:=12

include $(INCLUDE_DIR)/package.mk

define Package/veci-v2-runtime
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI v2 read-only exact-board health provider (development)
  DEPENDS:=+we5927-lte +veci-wifi-guardian +rpcd +jsonfilter +swconfig +flock +fwtool +ucert
endef

define Build/Compile
endef

define Package/veci-v2-runtime/description
  Small read-only hardware health API for ZBT-WE5927-DSIM.
  No driver or modem state changes; cannot claim AP or Internet readiness
  without real evidence. Source-only until field acceptance.
endef

define Package/veci-v2-runtime/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./veci2-verify-image $(1)/usr/libexec/veci2-verify-image
	$(INSTALL_BIN) ./veci2-lte-policy $(1)/usr/libexec/rpcd/veci.v2.lte
	$(INSTALL_BIN) ./veci2-wifi $(1)/usr/libexec/rpcd/veci.v2.wifi
	$(INSTALL_BIN) ./veci2-status $(1)/usr/libexec/rpcd/veci.v2
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./veci2-status-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-runtime.json
endef

$(eval $(call BuildPackage,veci-v2-runtime))
