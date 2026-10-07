"""All user-facing (English) texts in one place.

Lines are joined with CR by the session; adapters translate line endings.
"""

from . import VERSION

BANNER = "TinyBox {version} - {mailbox}"
HELLO = "Welcome to TinyBox {mailbox}, hello {call}."
NEW_MSGS = "You have {n} new message(s)."
NO_NEW_MSGS = "No new messages."

PROMPT = "TinyBox (A,B,C,H,J,K,L,R,S,V,?) > "
PROMPT_SYSOP = "TinyBox SYSOP (A,B,C,E,H,J,K,L,R,S,V,?) > "

HELP = [
    "TinyBox commands:",
    "  A          Abort output (stop a long list or message)",
    "  B          Bye (log off)",
    "  C          Chat: list the chat boards",
    "  C board    Chat: join a board (name or number)",
    "  DICT       Download the brocast dictionary (text, for the listener import)",
    "  H or ?     This help",
    "  J          Recently connected stations",
    "  K n        Kill message n (K n n ... for several)",
    "  KM         Kill all read messages to you",
    "  L          List messages",
    "             TS = Type (P private, B bulletin) + Status (N new, Y read)",
    "             3rd letter: $ waiting for forward, F forwarded, H held",
    "  LB / LP    List bulletins / private messages only",
    "  L@ area    List messages @ area or mailbox, e.g. L@ WW",
    "  L> call    List messages to call (L< call: from call)",
    "  LM         List messages to you",
    "  R n        Read message n (R n n ... for several)",
    "  RM         Read all unread messages to you",
    "  S call     Send private message (same as SP call)",
    "  SP call @ mailbox   Private message to a user of another mailbox,",
    "             e.g. SP OE1ABC @ OE1XAB.#WIE.AUT.EU",
    "  SB topic   Send bulletin, e.g. SB ALL  (SB ALL @ WW: to the whole network)",
    "             Optional at the end: $BID, e.g. SB DX @ EU $DX0815",
    "  V          Version",
]
HELP_SYSOP = [
    "Sysop:",
    "  E n field value   Edit header, field = TO, FROM, TYPE, STATUS, SUBJ, AT",
]

VERSION_TEXT = f"TinyBox {VERSION} - {{mode}}."
VERSION_LOCAL = "local mailbox, no forwarding"
VERSION_FWD = "mailbox {address}, forwarding on"
DICT_NONE = "No brocast dictionary available here."
DICT_INTRO = ("brocast dictionary v{version}, {lines} lines. Save this output (capture/log) "
              "and import it in the brocast listener.")
DICT_DONE = "Dictionary sent. Import the saved text under Status > Dictionary importieren."
BYE = "73, bye from TinyBox."
ABORTED = "Output aborted."

UNKNOWN_CMD = "Unknown command. Type H for help."
NO_SUCH_MSG = "No such message: {id}"
NOT_ALLOWED = "Not allowed."
INVALID_CALL = "Invalid callsign: {call}"
INVALID_VALUE = "Invalid value: {value}"
TOO_LARGE = "Message too long (max {max} bytes), discarded."
THIRD_PARTY_OFF = "Sorry, you can only send messages to the sysop {sysop}."
INVALID_ADDRESS = "Invalid address: {addr}  (e.g. OE1XAB.#WIE.AUT.EU or WW)"
DUPLICATE_BID = "BID {bid} is already known here - message not sent."
NO_FORWARD = "This mailbox does not forward. Leave out @ {addr} for local mail."

USAGE_R = "Usage: R n"
USAGE_K = "Usage: K n"
USAGE_S = "Usage: S call [@ mailbox] [$BID]  or  SB topic [@ area] [$BID]"
USAGE_E = "Usage: E n field value  (field = TO, FROM, TYPE, STATUS, SUBJ, AT)"

NO_MESSAGES = "No messages."
LIST_HEADER = " MSG# TS   SIZE TO        @BBS    FROM      DATE   UTC   SUBJECT"
LIST_ROW = ("{id:>5} {type}{status}{fwd} {size:>5} {to:<9} {at:<7} {frm:<9} {date} {time} "
            "{subject}")

READ_HEADER = [
    "Msg# {id}  Type/Status: {type}{status}{fwd}  BID: {bid}",
    "From: {frm}  To: {to}{at}",
    "Date: {date}",
    "Subject: {subject}",
    "",
]
HELD_NOTE = "*** Held: {note}"
READ_END = "[End of message {id}]"

KILLED = "Msg {id} killed."
KILLED_NONE = "No read messages to kill."
EDITED = "Msg {id} updated."

SUBJECT_PROMPT = "Subject: "
BODY_PROMPT = "Enter message, end with /EX or ^Z  (/AB = cancel):"
SAVED = "Msg {id} saved."
CANCELLED = "Message cancelled."
INTERNAL_ERROR = "*** Internal error, command not completed. Sysop is informed."

# chat boards
CHAT_OFF = "Chat is not available here."
CHAT_NOT_CONSOLE = "The chat is for mailbox users (radio/telnet), not on the console."
CHAT_ACTIVE = "{n} station(s) in the chat right now - type C to see the boards."
CHAT_LIST_HEADER = " #  BOARD    KEEP  USERS  DESCRIPTION"
CHAT_LIST_ROW = "{n:>2}  {board:<8} {keep:<5} {users:>5}  {desc}"
CHAT_LIST_FOOT = "Join with C board (or C n). KEEP: history time, live = not stored."
CHAT_NO_BOARD = "No such chat board: {board}"
CHAT_ALREADY = "You are already in {board}."
CHAT_HEADER = "*** Chat board {board} - {desc} [{keep}]"
CHAT_LIVE_NOTE = "Live board: nothing is stored, only stations here now read along."
CHAT_HISTORY = "--- Last messages ({keep}, UTC) ---"
CHAT_HISTORY_ROW = "{time} {call}: {text}"
CHAT_HISTORY_END = "--- End of history ---"
CHAT_HISTORY_NONE = "No messages in the last {keep}."
CHAT_WHO = "In this board: {calls}"
CHAT_ALONE = "Nobody else is here right now."
CHAT_HINT = "Type your text and press Enter. /H help, /Q back to the mailbox."
CHAT_LINE = "{call}: {text}"
CHAT_JOINED = "*** {call} joined {board}"
CHAT_LEFT = "*** {call} left {board}{reason}"
CHAT_REASON_DISC = " (disconnected)"
CHAT_BACK = "Left chat {board}, back in the mailbox."
CHAT_CUT = "(Line cut to {max} characters.)"
CHAT_UNKNOWN = "Unknown chat command. /H for help."
CHAT_HELP = [
    "Chat commands (everything else is sent to the board):",
    "  /Q         Back to the mailbox (also /EX or ^Z)",
    "  /W         Who is in this board",
    "  /L         List all boards",
    "  /J board   Change to another board",
    "  /H         This help",
]

JLOG_HEADER = "Call       Last seen (UTC)   Count"
JLOG_ROW = "{call:<10} {last:<17} {count:>5}"
JLOG_EMPTY = "No stations logged yet."

BUSY = "Sorry, TinyBox is busy. Please try again later."
IDLE_TIMEOUT = "Idle timeout, disconnecting. 73."

DISC_BY_SYSOP = "Disconnected by sysop. 73."
SHUTDOWN = "TinyBox is shutting down. 73."

# sysop console only
CONSOLE_BANNER = "*** TinyBox sysop console - type H for help ***"
HELP_CONSOLE = [
    "Console:",
    "  W          Who is connected",
    "  MON [ON|OFF]  Live monitor of user sessions",
    "  DISC call  Disconnect a user",
    "  STATUS     Mailbox status",
    "  WEB        Show the web GUI login link",
    "  FWD        Forward status of all partners",
    "  FWD call   Connect to a partner mailbox now",
    "  FWQ        Messages waiting for forwarding",
    "  HOLD n     Keep message n from forwarding (held, only the sysop sees it)",
    "  REL n      Release message n: forward it, or make it a normal local message",
    "  SHUTDOWN   Stop TinyBox",
]
CONSOLE_NO_BYE = "This is the local console. Use SHUTDOWN to stop TinyBox."
WHO_HEADER = "Call       Via     Since (UTC)       State"
WHO_ROW = "{call:<10} {via:<7} {since:<17} {state}"
WHO_EMPTY = "No users connected."
MON_STATE = "Monitor is {state}."
DISC_DONE = "{call} disconnected."
DISC_NONE = "{call} is not connected."
USAGE_DISC = "Usage: DISC call"
STATUS_LINES = [
    "TinyBox {version}  mailbox {mailbox}  sysop {sysop}",
    "Up since:  {since}",
    "Direwolf:  {agw}",
    "Users:     {users} of {max_users}",
    "Messages:  {msgs} ({private} private, {bulletins} bulletins, {unread} unread)",
    "Data:      {data_dir}",
]
SHUTTING_DOWN = "Shutting down ..."
FWD_OFF = "Forwarding is off ([forward] enabled = no)."
FWD_START = "Connecting to {call} ..."
FWD_DONE = "Forward {call}: {result}"
FWD_FAILED = "Forward {call} failed: {error}"
FWQ_EMPTY = "Forward queue is empty."
FWQ_HEADER = "Partner  Msg#  State  Since (UTC)"
FWQ_ROW = "{partner:<8} {id:>4}  {state:<6} {changed}"
USAGE_HOLD = "Usage: HOLD n  /  REL n"
HELD = "Msg {id} held."
RELEASED = {"$": "Msg {id} released, queued for forwarding.",
            "": "Msg {id} released, local message.",
            "H": "Msg {id}: no partner for {at} - still held."}

# telnet test port only
TELNET_LOGIN = "Callsign: "
TELNET_BAD_CALL = "Invalid callsign."
TELNET_TEST_NOTE = "*** TinyBox telnet test port (local only) ***"
