import logging
import re

from uaclient.entitlements import base
from uaclient import apt, exceptions, status
from uaclient import util
from uaclient.status import ApplicationStatus


SNAP_CMD = "/usr/bin/snap"
SNAP_INSTALL_RETRIES = [0.5, 1.0, 5.0]
LIVEPATCH_RETRIES = [0.5, 1.0]

try:
    from typing import Any, Callable, Dict, Tuple  # noqa: F401

    StaticAffordance = Tuple[str, Callable[[], Any], bool]
except ImportError:
    # typing isn't available on trusty, so ignore its absence
    pass

ERROR_MSG_MAP = {
    "Unknown Auth-Token": "Invalid Auth-Token provided to livepatch.",
    "unsupported kernel": "Your running kernel is not supported by Livepatch.",
}


class LivepatchEntitlement(base.UAEntitlement):

    help_doc_url = "https://ubuntu.com/security/livepatch"
    name = "livepatch"
    title = "Livepatch"
    description = "Canonical Livepatch service"

    @property
    def static_affordances(self) -> "Tuple[StaticAffordance, ...]":
        # Use a lambda so we can mock util.is_container in tests
        from uaclient.entitlements.fips import FIPSEntitlement
        from uaclient.entitlements.fips import FIPSUpdatesEntitlement

        fips_ent = FIPSEntitlement(self.cfg)
        fips_update_ent = FIPSUpdatesEntitlement(self.cfg)
        enabled_status = ApplicationStatus.ENABLED

        is_fips_enabled = bool(
            fips_ent.application_status()[0] == enabled_status
        )
        is_fips_updates_enabled = bool(
            fips_update_ent.application_status()[0] == enabled_status
        )

        return (
            (
                "Cannot install Livepatch on a container.",
                lambda: util.is_container(),
                False,
            ),
            (
                "Cannot enable Livepatch when FIPS is enabled.",
                lambda: is_fips_enabled,
                False,
            ),
            (
                "Cannot enable Livepatch when FIPS Updates is enabled.",
                lambda: is_fips_updates_enabled,
                False,
            ),
        )

    def _perform_enable(self) -> bool:
        """Enable specific entitlement.

        @return: True on success, False otherwise.
        """
        if not util.which("/snap/bin/canonical-livepatch"):
            if not util.which(SNAP_CMD):
                print("Installing snapd")
                print(status.MESSAGE_APT_UPDATING_LISTS)
                try:
                    apt.run_apt_command(
                        ["apt-get", "update"], status.MESSAGE_APT_UPDATE_FAILED
                    )
                except exceptions.UserFacingError as e:
                    logging.debug(
                        "Trying to install snapd."
                        " Ignoring apt-get update failure: %s",
                        str(e),
                    )
                util.subp(
                    ["apt-get", "install", "--assume-yes", "snapd"],
                    capture=True,
                    retry_sleeps=apt.APT_RETRIES,
                )
            elif "snapd" not in apt.get_installed_packages():
                raise exceptions.UserFacingError(
                    "/usr/bin/snap is present but snapd is not installed;"
                    " cannot enable {}".format(self.title)
                )

            try:
                util.subp(
                    [SNAP_CMD, "wait", "system", "seed.loaded"], capture=True
                )
            except util.ProcessExecutionError as e:
                if re.search(r"unknown command .*wait", str(e).lower()):
                    logging.warning(
                        status.MESSAGE_SNAPD_DOES_NOT_HAVE_WAIT_CMD
                    )
                else:
                    raise

            print("Installing canonical-livepatch snap")
            try:
                util.subp(
                    [SNAP_CMD, "install", "canonical-livepatch"],
                    capture=True,
                    retry_sleeps=SNAP_INSTALL_RETRIES,
                )
            except util.ProcessExecutionError as e:
                msg = "Unable to install Livepatch client: " + str(e)
                raise exceptions.UserFacingError(msg)
        return self.setup_livepatch_config(
            process_directives=True, process_token=True
        )

    def setup_livepatch_config(
        self, process_directives: bool = True, process_token: bool = True
    ) -> bool:
        """Processs configuration setup for livepatch directives.

        :param process_directives: Boolean set True when directives should be
            processsed.
        :param process_token: Boolean set True when token should be
            processsed.
        """
        entitlement_cfg = self.cfg.entitlements.get(self.name)
        if process_directives:
            try:
                process_config_directives(entitlement_cfg)
            except util.ProcessExecutionError as e:
                msg = "Unable to configure Livepatch: " + str(e)
                print(msg)
                logging.error(msg)
                return False
        if process_token:
            livepatch_token = entitlement_cfg.get("resourceToken")
            if not livepatch_token:
                logging.debug(
                    "No specific resourceToken present. Using machine token as"
                    " %s credentials",
                    self.title,
                )
                livepatch_token = self.cfg.machine_token["machineToken"]
            application_status, _details = self.application_status()
            if application_status != status.ApplicationStatus.DISABLED:
                logging.info(
                    "Disabling %s prior to re-attach with new token",
                    self.title,
                )
                try:
                    util.subp(["/snap/bin/canonical-livepatch", "disable"])
                except util.ProcessExecutionError as e:
                    logging.error(str(e))
                    return False
            try:
                util.subp(
                    [
                        "/snap/bin/canonical-livepatch",
                        "enable",
                        livepatch_token,
                    ],
                    capture=True,
                )
            except util.ProcessExecutionError as e:
                msg = "Unable to enable Livepatch: "
                for error_message, print_message in ERROR_MSG_MAP.items():
                    if error_message in str(e):
                        msg += print_message
                        break
                if msg == "Unable to enable Livepatch: ":
                    msg += str(e)
                print(msg)
                return False
            print("Canonical livepatch enabled.")
        return True

    def disable(self, silent=False):
        """Disable specific entitlement

        @return: True on success, False otherwise.
        """
        if not self.can_disable(silent):
            return False
        if not util.which("/snap/bin/canonical-livepatch"):
            return True
        util.subp(["/snap/bin/canonical-livepatch", "disable"], capture=True)
        return True

    def application_status(self) -> "Tuple[ApplicationStatus, str]":
        status = (ApplicationStatus.ENABLED, "")

        if not util.which("/snap/bin/canonical-livepatch"):
            return (
                ApplicationStatus.DISABLED,
                "canonical-livepatch snap is not installed.",
            )

        try:
            util.subp(
                ["/snap/bin/canonical-livepatch", "status"],
                retry_sleeps=LIVEPATCH_RETRIES,
            )
        except util.ProcessExecutionError as e:
            # TODO(May want to parse INACTIVE/failure assessment)
            logging.debug("Livepatch not enabled. %s", str(e))
            status = (ApplicationStatus.DISABLED, str(e))
        return status

    def process_contract_deltas(
        self,
        orig_access: "Dict[str, Any]",
        deltas: "Dict[str, Any]",
        allow_enable: bool = False,
    ) -> bool:
        """Process any contract access deltas for this entitlement.

        :param orig_access: Dictionary containing the original
            resourceEntitlement access details.
        :param deltas: Dictionary which contains only the changed access keys
        and values.
        :param allow_enable: Boolean set True if allowed to perform the enable
            operation. When False, a message will be logged to inform the user
            about the recommended enabled service.

        :return: True when delta operations are processed; False when noop.
        """
        if super().process_contract_deltas(orig_access, deltas, allow_enable):
            return True  # Already processed parent class deltas

        delta_entitlement = deltas.get("entitlement", {})
        process_enable_default = delta_entitlement.get("obligations", {}).get(
            "enabledByDefault", False
        )

        if process_enable_default:
            enable_success, _ = self.enable()
            return enable_success

        application_status, _ = self.application_status()
        if application_status == status.ApplicationStatus.DISABLED:
            return True  # only operate on changed directives when ACTIVE
        delta_directives = delta_entitlement.get("directives", {})
        supported_deltas = set(["caCerts", "remoteServer"])
        process_directives = bool(
            supported_deltas.intersection(delta_directives)
        )
        process_token = bool(deltas.get("resourceToken", False))
        if any([process_directives, process_token]):
            logging.info("Updating '%s' on changed directives.", self.name)
            return self.setup_livepatch_config(
                process_directives=process_directives,
                process_token=process_token,
            )
        return True


def process_config_directives(cfg):
    """Process livepatch configuration directives.

    We process caCerts before remoteServer because changing remote-server
    in the canonical-livepatch CLI performs a PUT against the new server name.
    If new caCerts were required for the new remoteServer, this
    canonical-livepatch client PUT could fail on unmatched old caCerts.

    @raises: ProcessExecutionError if unable to configure livepatch.
    """
    if not cfg:
        return
    directives = cfg.get("entitlement", {}).get("directives", {})
    ca_certs = directives.get("caCerts")
    if ca_certs:
        util.subp(
            [
                "/snap/bin/canonical-livepatch",
                "config",
                "ca-certs={}".format(ca_certs),
            ],
            capture=True,
        )
    remote_server = directives.get("remoteServer", "")
    if remote_server.endswith("/"):
        remote_server = remote_server[:-1]
    if remote_server:
        util.subp(
            [
                "/snap/bin/canonical-livepatch",
                "config",
                "remote-server={}".format(remote_server),
            ],
            capture=True,
        )
