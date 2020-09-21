@uses.config.contract_token
@uses.config.machine_type.lxd.container
Feature: Command behaviour when upgrading across Ubuntu LTS releases

    @series.bionic
    Scenario Outline: Attached upgrade across LTS releases
        Given a `<release>` machine with ubuntu-advantage-tools installed
        When I attach `contract_token` with sudo
        And I run `apt-get dist-upgrade --assume-yes` with sudo
        And I create the file `/etc/update-manager/release-upgrades.d/ua-test.cfg` with the following
        """
        [Sources]
        AllowThirdParty=True
        """
        Then I verify that running `do-release-upgrade <devel_flag> -q -f DistUpgradeViewNonInteractive` `with sudo` exits `0`
        When I reboot
        And I run `egrep "<release>|disabled" /etc/apt/sources.list.d/*` as non-root
        Then I will see the following on stdout:
            """
            """
        Examples: ubuntu release
           | release | devel_flag |
           | bionic  | -d         |
