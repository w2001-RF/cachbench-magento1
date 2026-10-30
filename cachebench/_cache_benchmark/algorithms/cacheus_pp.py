"""
CACHEUS++ - hybrid cache replacement for e-commerce workloads

Extends CACHEUS (USENIX FAST'21) with:
  1. Regret minimization over three experts (LRU, LFU, cost-aware GDSF).
     Each expert keeps a ghost history of the keys it evicted; a miss on a
     ghost key penalizes that expert, discounted by how long ago it evicted
     the key (LeCaR, USENIX HotStorage'18).
  2. Adaptive learning rate (CACHEUS): the regret learning rate is tuned once
     per window by hill-climbing on the observed hit rate.
  3. Lightweight RL layer: REINFORCE on a linear softmax policy whose logits
     are log(regret weights) + theta_e . state. With theta = 0 this is plain
     CACHEUS; theta learns which expert to trust in which cache state.
  4. Learned admission ("cache-worthiness"): online logistic regression on
     size, frequency, recency, miss cost and category, trained from whether
     admitted keys get hit before eviction and whether rejected keys come back.
  5. Miss cost: per-category tier costs (e.g. DB fetch vs CDN fetch, or AWS
     cost per fetch) or request.metadata["miss_cost"], used by the GDSF expert
     and the admission model.
"""

import heapq
import math
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..base import CacheAlgorithm
from ..models import CacheRequest

LRU, LFU, GDSF = 0, 1, 2
EXPERT_NAMES = ("lru", "lfu", "gdsf")
NUM_EXPERTS = 3

NUM_CATEGORY_BUCKETS = 8
ADMIT_DIM = 5 + NUM_CATEGORY_BUCKETS  # bias, size, freq, recency, cost + categories
STATE_DIM = 5  # bias, prev hit rate, cold fraction, incoming size, category share


@dataclass
class _Entry:
    size: int
    category: str
    cost: float
    freq: int
    last_access: int
    version: int = 0
    hits: int = 0
    labeled: bool = False
    admit_features: Optional[np.ndarray] = None


class CACHEUSPlusPlus(CacheAlgorithm):
    """
    CACHEUS++ - regret minimization + policy gradient eviction + learned admission
    """

    LR_STEP = 0.1          # relative learning-rate change per window
    LR_BOUNDS = (1e-3, 1.0)
    WEIGHT_FLOOR = 1e-3    # keeps every expert selectable
    THETA_CLIP = 5.0
    BASELINE_DECAY = 0.01  # EMA rate of the REINFORCE reward baseline
    ADMISSION_L2 = 1e-4

    def __init__(self, cache_size: int, name: str = "CACHEUS++",
                 learning_rate: float = 0.45,
                 rl_learning_rate: float = 0.05,
                 admission_learning_rate: float = 0.05,
                 admission_threshold: float = 0.1,  # reject only confident one-hit wonders
                 exploration_rate: float = 0.05,
                 min_admission_samples: int = 200,
                 max_object_fraction: float = 0.1,
                 window_size: int = 1000,
                 min_history: int = 64,
                 metadata_capacity: int = 100_000,
                 tier_costs: Optional[Dict[str, float]] = None,
                 seed: Optional[int] = None):
        super().__init__(cache_size, name)
        self.learning_rate = learning_rate
        self.rl_learning_rate = rl_learning_rate
        self.admission_learning_rate = admission_learning_rate
        self.admission_threshold = admission_threshold
        self.exploration_rate = exploration_rate
        self.min_admission_samples = min_admission_samples
        self.max_object_fraction = max_object_fraction
        self.window_size = window_size
        self.min_history = min_history
        self.metadata_capacity = metadata_capacity
        self.tier_costs = tier_costs or {}
        self.seed = seed
        self._init_state()

    def reset(self):
        self._init_state()

    def _init_state(self):
        self.cache = {}
        self.current_size = 0
        self._rng = np.random.default_rng(self.seed)
        self._clock = 0

        # Resident entries and per-expert eviction orders
        self._meta: Dict[str, _Entry] = {}
        self._lru: "OrderedDict[str, None]" = OrderedDict()
        self._lfu_heap: List[Tuple[int, int, int, str]] = []  # (freq, last_access, version, key)
        self._gdsf_heap: List[Tuple[float, int, str]] = []    # (priority, version, key)
        self._gdsf_inflation = 0.0
        self._cat_bytes: Dict[str, int] = defaultdict(int)
        self._cold_entries = 0  # resident entries never hit since admission

        # Regret minimization
        self.weights = np.ones(NUM_EXPERTS) / NUM_EXPERTS
        self._history: List["OrderedDict[str, Tuple[int, np.ndarray]]"] = [
            OrderedDict() for _ in range(NUM_EXPERTS)
        ]
        self._lr = self.learning_rate
        self._lr_direction = 1.0
        self._prev_hit_rate = 0.0
        self._zero_windows = 0
        self._win_hits = 0
        self._win_requests = 0

        # Policy gradient layer
        self.theta = np.zeros((NUM_EXPERTS, STATE_DIM))
        self._reward_baseline = 0.0

        # Admission model
        self.admission_w = np.zeros(ADMIT_DIM)
        self._admission_samples = 0
        self._rejections = 0
        self._rejected: "OrderedDict[str, np.ndarray]" = OrderedDict()
        self._pending: Optional[Tuple[str, np.ndarray]] = None
        self._category_index: Dict[str, int] = {}

        # Access statistics for keys whether cached or not: key -> [count, last_seen]
        self._seen: "OrderedDict[str, List[int]]" = OrderedDict()
        self._last_key: Optional[str] = None
        self._last_gap: Optional[int] = None

        self.expert_evictions = np.zeros(NUM_EXPERTS, dtype=int)

    # ------------------------------------------------------------------
    # CacheAlgorithm API
    # ------------------------------------------------------------------

    def get(self, request: CacheRequest) -> bool:
        self._clock += 1
        key = request.key
        self._observe_access(key)

        entry = self._meta.get(key)
        if entry is not None:
            entry.freq += 1
            entry.hits += 1
            entry.last_access = self._clock
            if entry.hits == 1:
                self._cold_entries -= 1
            if not entry.labeled and entry.admit_features is not None:
                self._train_admission(entry.admit_features, 1.0)
                entry.labeled = True
            self._lru.move_to_end(key)
            self._touch(key, entry)
            self._record_request(hit=True)
            return True

        self._on_ghost_miss(key)
        rejected_features = self._rejected.pop(key, None)
        if rejected_features is not None:
            # Rejected key came back: admitting it would have paid off
            self._train_admission(rejected_features, 1.0)
        self._record_request(hit=False)
        return False

    def put(self, request: CacheRequest) -> int:
        evictions = 0
        if request.key in self.cache or request.size > self.cache_size:
            return evictions

        features = self._take_pending_features(request)

        while self.current_size + request.size > self.cache_size and self.cache:
            victim, expert, state = self._select_victim(request)
            self._evict(victim)
            self._add_history(expert, victim, state)
            self.expert_evictions[expert] += 1
            evictions += 1

        self._insert(request, features)
        return evictions

    def should_cache(self, request: CacheRequest) -> bool:
        """Learned admission: admit if predicted cache-worthiness passes the threshold"""
        if request.key in self.cache:
            return True
        if request.size > self.cache_size * self.max_object_fraction:
            return False

        features = self._admission_features(request)
        self._pending = (request.key, features)

        # Free space costs nothing; early on the model has not learned anything yet
        if self.current_size + request.size <= self.cache_size:
            return True
        if self._admission_samples < self.min_admission_samples:
            return True
        # Exploration keeps labels flowing for keys the model would reject
        if self._rng.random() < self.exploration_rate:
            return True
        if self.admission_probability(features) >= self.admission_threshold:
            return True

        self._remember_rejected(request.key, features)
        self._rejections += 1
        return False

    # ------------------------------------------------------------------
    # Eviction: experts, regret minimization, policy gradient
    # ------------------------------------------------------------------

    def _select_victim(self, incoming: CacheRequest) -> Tuple[str, int, np.ndarray]:
        state = self._eviction_state(incoming)
        probs = self._policy(state)
        expert = int(self._rng.choice(NUM_EXPERTS, p=probs))

        if expert == LRU:
            victim = next(iter(self._lru))
        elif expert == LFU:
            victim = self._peek(self._lfu_heap)
        else:
            victim = self._peek(self._gdsf_heap)
            if victim is not None:
                self._gdsf_inflation = self._gdsf_heap[0][0]

        if victim is None:  # heaps always cover resident keys; defensive fallback
            victim, expert = next(iter(self._lru)), LRU
        return victim, expert, state

    def _policy(self, state: np.ndarray) -> np.ndarray:
        logits = np.log(self.weights) + self.theta @ state
        logits -= logits.max()
        probs = np.exp(logits)
        return probs / probs.sum()

    def _eviction_state(self, incoming: CacheRequest) -> np.ndarray:
        n = len(self.cache)
        cold_fraction = self._cold_entries / n if n else 0.0
        size_ratio = math.log1p(incoming.size) / math.log1p(self.cache_size)
        category_share = (self._cat_bytes.get(incoming.category, 0) / self.current_size
                          if self.current_size else 0.0)
        return np.array([1.0, self._prev_hit_rate, cold_fraction, size_ratio, category_share])

    def _on_ghost_miss(self, key: str):
        for expert in range(NUM_EXPERTS):
            item = self._history[expert].pop(key, None)
            if item is None:
                continue
            evicted_at, state = item
            # LeCaR discount: regret fades with time since eviction
            discount = 0.005 ** (1.0 / max(1, len(self.cache)))
            regret = discount ** (self._clock - evicted_at)
            self.weights[expert] *= math.exp(-self._lr * regret)
            self._normalize_weights()
            self._policy_gradient(expert, state, -regret)

    def _add_history(self, expert: int, key: str, state: np.ndarray):
        history = self._history[expert]
        history[key] = (self._clock, state)
        limit = max(self.min_history, len(self.cache))
        while len(history) > limit:
            _, (_, old_state) = history.popitem(last=False)
            # Evicted key never came back: the eviction was a good one
            self._policy_gradient(expert, old_state, 0.0)

    def _policy_gradient(self, expert: int, state: np.ndarray, reward: float):
        """REINFORCE update for a linear softmax policy"""
        probs = self._policy(state)
        advantage = reward - self._reward_baseline
        self._reward_baseline += self.BASELINE_DECAY * (reward - self._reward_baseline)

        grad = -np.outer(probs, state)
        grad[expert] += state
        self.theta += self.rl_learning_rate * advantage * grad
        np.clip(self.theta, -self.THETA_CLIP, self.THETA_CLIP, out=self.theta)

    def _normalize_weights(self):
        self.weights /= self.weights.sum()
        np.maximum(self.weights, self.WEIGHT_FLOOR, out=self.weights)
        self.weights /= self.weights.sum()

    def _record_request(self, hit: bool):
        self._win_hits += hit
        self._win_requests += 1
        if self._win_requests >= self.window_size:
            self._end_window()

    def _end_window(self):
        """CACHEUS-style hill climbing on the learning rate"""
        hit_rate = self._win_hits / self._win_requests

        if hit_rate < self._prev_hit_rate:
            self._lr_direction = -self._lr_direction

        if hit_rate == 0:
            self._zero_windows += 1
            if self._zero_windows >= 3:
                self._lr = self.learning_rate
                self._zero_windows = 0
        else:
            self._zero_windows = 0

        lo, hi = self.LR_BOUNDS
        self._lr = min(hi, max(lo, self._lr * (1 + self.LR_STEP * self._lr_direction)))
        self._prev_hit_rate = hit_rate
        self._win_hits = 0
        self._win_requests = 0

    # ------------------------------------------------------------------
    # Resident set bookkeeping
    # ------------------------------------------------------------------

    def _insert(self, request: CacheRequest, features: np.ndarray):
        key = request.key
        seen = self._seen.get(key)
        entry = _Entry(
            size=request.size,
            category=request.category,
            cost=self._miss_cost(request),
            freq=seen[0] if seen else 1,
            last_access=self._clock,
            admit_features=features,
        )
        self.cache[key] = request
        self._meta[key] = entry
        self._lru[key] = None
        self.current_size += request.size
        self._cat_bytes[request.category] += request.size
        self._cold_entries += 1

        for history in self._history:
            history.pop(key, None)
        self._rejected.pop(key, None)
        self._touch(key, entry)

    def _evict(self, key: str):
        entry = self._meta.pop(key)
        del self.cache[key]
        del self._lru[key]
        self.current_size -= entry.size
        self._cat_bytes[entry.category] -= entry.size
        if entry.hits == 0:
            self._cold_entries -= 1
        if not entry.labeled and entry.admit_features is not None:
            # Admitted but never hit: admission was wasted
            self._train_admission(entry.admit_features, 0.0)

    def _touch(self, key: str, entry: _Entry):
        """Push fresh heap entries; older ones become stale via the version number"""
        entry.version += 1
        heapq.heappush(self._lfu_heap, (entry.freq, entry.last_access, entry.version, key))
        priority = self._gdsf_inflation + entry.freq * entry.cost / max(1, entry.size)
        heapq.heappush(self._gdsf_heap, (priority, entry.version, key))

        if len(self._lfu_heap) > 4 * len(self._meta) + 1024:
            self._compact_heaps()

    def _peek(self, heap: list) -> Optional[str]:
        while heap:
            version, key = heap[0][-2], heap[0][-1]
            entry = self._meta.get(key)
            if entry is not None and entry.version == version:
                return key
            heapq.heappop(heap)
        return None

    def _compact_heaps(self):
        self._lfu_heap = [item for item in self._lfu_heap if self._is_current(item)]
        self._gdsf_heap = [item for item in self._gdsf_heap if self._is_current(item)]
        heapq.heapify(self._lfu_heap)
        heapq.heapify(self._gdsf_heap)

    def _is_current(self, item: tuple) -> bool:
        entry = self._meta.get(item[-1])
        return entry is not None and entry.version == item[-2]

    def _miss_cost(self, request: CacheRequest) -> float:
        if "miss_cost" in request.metadata:
            return float(request.metadata["miss_cost"])
        return float(self.tier_costs.get(request.category, 1.0))

    # ------------------------------------------------------------------
    # Admission model
    # ------------------------------------------------------------------

    def admission_probability(self, features: np.ndarray) -> float:
        z = float(self.admission_w @ features)
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))

    def _admission_features(self, request: CacheRequest) -> np.ndarray:
        seen = self._seen.get(request.key)
        freq = seen[0] if seen else 0
        gap = self._last_gap if self._last_key == request.key else None
        cost = self._miss_cost(request)

        x = np.zeros(ADMIT_DIM)
        x[0] = 1.0
        x[1] = math.log1p(request.size) / math.log1p(self.cache_size)
        x[2] = min(1.0, math.log1p(freq) / math.log1p(1000))
        x[3] = 1.0 if gap is None else min(1.0, math.log1p(gap) / math.log1p(self.metadata_capacity))
        x[4] = cost / (1.0 + cost)
        x[5 + self._category_bucket(request.category)] = 1.0
        return x

    def _category_bucket(self, category: str) -> int:
        bucket = self._category_index.get(category)
        if bucket is None:
            # Deterministic across runs (unlike hash()); overflow shares the last bucket
            bucket = min(len(self._category_index), NUM_CATEGORY_BUCKETS - 1)
            self._category_index[category] = bucket
        return bucket

    def _take_pending_features(self, request: CacheRequest) -> np.ndarray:
        pending, self._pending = self._pending, None
        if pending is not None and pending[0] == request.key:
            return pending[1]
        return self._admission_features(request)

    def _train_admission(self, features: np.ndarray, label: float):
        p = self.admission_probability(features)
        self.admission_w += self.admission_learning_rate * (
            (label - p) * features - self.ADMISSION_L2 * self.admission_w
        )
        self._admission_samples += 1

    def _remember_rejected(self, key: str, features: np.ndarray):
        self._rejected[key] = features
        self._rejected.move_to_end(key)
        limit = max(self.min_history, len(self.cache))
        while len(self._rejected) > limit:
            _, old_features = self._rejected.popitem(last=False)
            # Rejected key did not come back: rejecting it was right
            self._train_admission(old_features, 0.0)

    def _observe_access(self, key: str):
        seen = self._seen.get(key)
        if seen is None:
            self._last_gap = None
            self._seen[key] = [1, self._clock]
            if len(self._seen) > self.metadata_capacity:
                self._seen.popitem(last=False)
        else:
            self._last_gap = self._clock - seen[1]
            seen[0] += 1
            seen[1] = self._clock
            self._seen.move_to_end(key)
        self._last_key = key

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, object]:
        """Internal state useful for analysis and thesis figures"""
        return {
            "expert_weights": dict(zip(EXPERT_NAMES, self.weights.round(4).tolist())),
            "expert_evictions": dict(zip(EXPERT_NAMES, self.expert_evictions.tolist())),
            "learning_rate": round(self._lr, 4),
            "admission_samples": self._admission_samples,
            "admission_rejections": self._rejections,
        }
