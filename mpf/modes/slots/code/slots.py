import random
from mpf.core.mode import Mode
from mpf.core.utility_functions import Util
import logging

DEFAULT_SLOT_COUNT = 3

class Slots(Mode):

  """Mode which plays a slot-machine to cycle and align awards."""

  __slots__ = ["_items", "_lock_idxs", "_positioning", "_rotate_method", "_slot_count", "_slot_events", "_slots"]

  def __init__(self, machine, config, name, path):
    self._items = []
    self._slot_count = 3
    
    self._rotate_method = None
    self._lock_idxs = set()
    super().__init__(machine, config, name, path)

    self.log = logging.getLogger("{}Slots".format(self.name))

  def mode_init(self):
    super().mode_init()
    mode_settings = self.config.get("mode_settings", {})
    self._lock_idxs = None if mode_settings.get("lock_matches") == False else set()
    self._positioning = mode_settings.get("initial_position_type", "different")
    self._rotate_method = mode_settings.get("rotate_method", "sequential")
    self._slot_count = mode_settings.get("slot_count", DEFAULT_SLOT_COUNT)
    self._slots = [None] * self._slot_count
    self._slot_events = [None] * self._slot_count
    
    if mode_settings.get("debug"):
      self.log.setLevel(10)

    if self._lock_idxs is not None and self._positioning == "same":
      raise AssertionError("Slots with initial_position_type 'same' cannot use lock_matches")

    for award, award_config in mode_settings.get("slot_awards", {}).items():
      award_dict = { "name": award }
      award_dict.update(award_config)
      self._items.append(award_dict)

    self._slot_events = [Util.string_to_list(mode_settings.get("slot_{}_hit_events".format(x+1), []))
      for x in range(self._slot_count)]

  def mode_start(self, **kwargs):
    self._randomize_slots()
    for idx, events in enumerate(self._slot_events):
      if not events:
        raise AssertionError("Slot position {} has no hit events".format(idx+1))
      self._register_events(idx, events, self._on_slot_hit)

    self.log.debug("Created slots: {}".format(self._slots))

  def _post_slot(self, slot_num, **kwargs):
    params = dict()
    for args in [self._slots[slot_num], kwargs]:
      params.update(args)
    self.machine.events.post("slots_{}_{}_updated".format(self.name, slot_num), **params)

  def _randomize_slots(self):
    initial_position_type = self.config.get("initial_position_type", "different")
    if initial_position_type == "different":
      chosen_items = []
      for x in range(self._slot_count):
        self._slots[x] = random.choice([item for item in self._items if not item in chosen_items])
        chosen_items.append(self._slots[x])
        self._post_slot(x, is_reset=True)
    elif initial_position_type == "same":
      item = random.choice(self._items)
      for x in range(self._slot_count):
        self._slots[x] = item
        self._post_slot(x, is_reset=True)

  def _register_events(self, slot_num, events, handler):
    for event in events:
      self.add_mode_event_handler(event, handler, slot_num=slot_num)

  def _on_slot_hit(self, **kwargs):
    slot_num = kwargs["slot_num"]
    current_item = self._slots[slot_num]

    if slot_num in self._lock_idxs:
      self.log.debug("Slot {} is locked, skipping handler".format(slot_num))
      return;

    self.log.debug("Updating slot {} with {}".format(slot_num, self._rotate_method))
    if self._rotate_method == "sequential":
      current_idx = self._items.index(current_item)
      next_idx = (current_idx + 1) % len(self._items)
      self.log.debug(" - Sequence advance from item {} to item {}".format(current_idx, next_idx))
      self._slots[slot_num] = self._items[next_idx]
    elif self._rotate_method == "random":
      self._slots[slot_num] = random.choice([item for item in self._items if item != current_item])
    self._post_slot(slot_num)

    # Look for all matching
    if self._slots.count(self._slots[0]) == len(self._slots):
      self.machine.events.post("slots_{}_complete".format(self.name), **self._slots[0])
      self.machine.events.post("slots_{}_{}_complete".format(self.name, self._slots[0]["name"]))
      self._randomize_slots()
      if self._lock_idxs is not None:
        self._lock_idxs.clear()

    # Look for duplicates to lock
    elif self._lock_idxs is not None:
      for idx, value in enumerate(self._slots):
        if self._slots.count(value) > 1:
          self._lock_idxs.add(idx)





