import enum


class TxtColor:
    OKGREEN = '\033[92m'
    DISABLEGREY = '\033[37m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


@enum.unique
class ApplicationStatus(enum.Enum):
    """
    An enum to represent the current application status of an entitlement
    """
    ENABLED = object()
    DISABLED = object()

    def to_operational_status(self) -> str:
        mapping = {
            ApplicationStatus.ENABLED: ACTIVE,
            ApplicationStatus.DISABLED: INACTIVE,
        }
        return mapping[self]


@enum.unique
class ContractStatus(enum.Enum):
    """
    An enum to represent whether a user is entitled to an entitlement

    (The value of each member is the string that will be used in status
    output.)
    """
    ENTITLED = 'entitled'
    UNENTITLED = 'none'


ACTIVE = 'active'
INACTIVE = 'inactive'
INAPPLICABLE = 'n/a'
NONE = 'none'
ESSENTIAL = 'essential'
STANDARD = 'standard'
ADVANCED = 'advanced'

# Colorized status output for terminal
STATUS_COLOR = {
    ACTIVE: TxtColor.OKGREEN + ACTIVE + TxtColor.ENDC,
    INACTIVE: TxtColor.FAIL + INACTIVE + TxtColor.ENDC,
    INAPPLICABLE: TxtColor.DISABLEGREY + INAPPLICABLE + TxtColor.ENDC,
    ContractStatus.ENTITLED.value: (
        TxtColor.OKGREEN + ContractStatus.ENTITLED.value + TxtColor.ENDC),
    NONE: TxtColor.DISABLEGREY + NONE + TxtColor.ENDC,
    ESSENTIAL: TxtColor.OKGREEN + ESSENTIAL + TxtColor.ENDC,
    STANDARD: TxtColor.OKGREEN + STANDARD + TxtColor.ENDC,
    ADVANCED: TxtColor.OKGREEN + ADVANCED + TxtColor.ENDC
}

MESSAGE_DISABLED_TMPL = '{title} disabled.'
MESSAGE_NONROOT_USER = 'This command must be run as root (try using sudo)'
MESSAGE_ALREADY_DISABLED_TMPL = """\
{title} is not currently enabled.\nSee `ua status`"""
MESSAGE_ENABLED_FAILED_TMPL = 'Could not enable {title}.'
MESSAGE_ENABLED_TMPL = '{title} enabled.'
MESSAGE_ALREADY_ENABLED_TMPL = '{title} is already enabled.\nSee `ua status`'
MESSAGE_INAPPLICABLE_ARCH_TMPL = """\
{title} is not available for platform {arch}.
Supported platforms are: {supported_arches}"""
MESSAGE_INAPPLICABLE_SERIES_TMPL = """\
{title} is not available for Ubuntu {series}."""
MESSAGE_INAPPLICABLE_KERNEL_TMPL = """\
{title} is not available for kernel {kernel}.
Supported flavors are: {supported_kernels}"""
MESSAGE_INAPPLICABLE_KERNEL_VER_TMPL = """\
{title} is not available for kernel {kernel}.
Minimum kernel version required: {min_kernel}"""
MESSAGE_UNENTITLED_TMPL = """\
This subscription is not entitled to {title}.
See `ua status` or https://ubuntu.com/advantage"""
MESSAGE_UNATTACHED = """\
This machine is not attached to a UA subscription.
See `ua attach` or https://ubuntu.com/advantage"""

STATUS_HEADER_TMPL = """\
Account: {account}
Subscription: {subscription}
Valid until: {expires}
Technical support level: {techSupportLevel}
"""
STATUS_SERVICE_HEADER = 'SERVICE'
STATUS_TMPL = '{name: <14}{entitled: <26}{status}'

MESSAGE_ATTACH_FAILURE_TMPL = """\
Could not attach machine. Error contacting server {url}"""
MESSAGE_ATTACH_SUCCESS_TMPL = """\
This machine is now attached to '{contract_name}'.
"""

MESSAGE_ENABLE_BY_DEFAULT_TMPL = 'Enabling default service {name}'
MESSAGE_ENABLE_BY_DEFAULT_MANUAL_TMPL = """\
Service {name} is recommended by default. To enable run `ua enable {name}`"""
MESSAGE_DETACH_SUCCESS = 'This machine is now detached'

MESSAGE_REFRESH_ENABLE = 'Refreshing contracts prior to enable'
MESSAGE_REFRESH_SUCCESS = 'Refreshed Ubuntu Advantage contracts.'
MESSAGE_REFRESH_FAILURE = 'Failure to refresh Ubuntu Advantage contracts.'


def format_tabular(status):
    """Format status dict for tabular output."""
    if not status['attached']:
        return MESSAGE_UNATTACHED
    tech_support_level = status['techSupportLevel']
    content = [STATUS_HEADER_TMPL.format(
        account=status['account'],
        subscription=status['subscription'],
        expires=status['expires'],
        techSupportLevel=STATUS_COLOR.get(tech_support_level,
                                          tech_support_level))]

    content.append(STATUS_SERVICE_HEADER)
    for service_status in status['services']:
        entitled = service_status['entitled']
        fmt_args = {
            'name': service_status['name'],
            'entitled': STATUS_COLOR.get(entitled, entitled),
            'status': STATUS_COLOR.get(
                service_status['status'], service_status['status'])}
        content.append(STATUS_TMPL.format(**fmt_args))
    content.append('\nEnable entitlements with `ua enable <service>`')
    return '\n'.join(content)
