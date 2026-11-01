<?php
/**
 * Portage PHP de CACHEUS++ (cache_benchmark, algorithms/cacheus_pp.py), décision par décision :
 * même générateur (numpy default_rng = PCG64), mêmes structures, mêmes calculs dans le même
 * ordre que numpy, pour donner les mêmes hits que Python.
 *
 * Seul écart possible : numpy calcule theta @ state avec le dgemv d'OpenBLAS, reproduit ici
 * pour un noyau AVX2 (voir dotState) ; sur un autre processeur l'arrondi du dernier bit peut
 * différer, ce qui ne change une décision qu'avec une probabilité négligeable.
 *
 * Interface de cache_benchmark : get(), shouldCache(), put() dans cet ordre, comme son runner.
 * Les clés sont des chaînes ; PHP convertit "123" en entier dans les clés de tableau, d'où
 * les (string) en sortie.
 */
class Aicache_CacheusPP_Algorithm
{
    const LRU = 0;
    const LFU = 1;
    const GDSF = 2;
    const NUM_EXPERTS = 3;
    const NUM_CATEGORY_BUCKETS = 8;
    const ADMIT_DIM = 13;   // biais, taille, fréquence, récence, coût + 8 catégories
    const STATE_DIM = 5;    // biais, hit rate précédent, part froide, taille entrante, part de catégorie

    const LR_STEP = 0.1;
    const LR_LO = 1e-3;
    const LR_HI = 1.0;
    const WEIGHT_FLOOR = 1e-3;
    const THETA_CLIP = 5.0;
    const BASELINE_DECAY = 0.01;
    const ADMISSION_L2 = 1e-4;

    public static $expertNames = array('lru', 'lfu', 'gdsf');

    public $cacheSize;
    public $learningRate = 0.45;
    public $rlLearningRate = 0.05;
    public $admissionLearningRate = 0.05;
    public $admissionThreshold = 0.1;
    public $explorationRate = 0.05;
    public $minAdmissionSamples = 200;
    public $maxObjectFraction = 0.1;
    public $windowSize = 1000;
    public $minHistory = 64;
    public $metadataCapacity = 100000;
    public $tierCosts = array();

    /** @var int[] clé -> taille (le dict cache d'origine) */
    public $cache = array();
    public $currentSize = 0;
    protected $rng;
    protected $clock = 0;

    /** @var Aicache_CacheusPP_Entry[] */
    protected $meta = array();
    protected $lru = array();
    protected $lfuHeap = array();     // [freq, last_access, version, clé]
    protected $gdsfHeap = array();    // [priorité, version, clé]
    protected $gdsfInflation = 0.0;
    protected $keptAfterCompact = 0;
    protected $catBytes = array();
    protected $coldEntries = 0;

    public $weights;
    protected $history;               // par expert : clé -> [instant d'éviction, état]
    protected $lr;
    protected $lrDirection = 1.0;
    protected $prevHitRate = 0.0;
    protected $zeroWindows = 0;
    protected $winHits = 0;
    protected $winRequests = 0;

    public $theta;
    protected $rewardBaseline = 0.0;

    public $admissionW;
    protected $admissionSamples = 0;
    protected $rejections = 0;
    protected $rejected = array();
    protected $pending = null;
    protected $categoryIndex = array();

    protected $seen = array();        // clé -> [compte, dernier accès]
    protected $lastKey = null;
    protected $lastGap = null;

    public $expertEvictions = array(0, 0, 0);

    public function __construct($cacheSize, array $params = array())
    {
        $this->cacheSize = (int) $cacheSize;
        $floats = array('learning_rate' => 'learningRate', 'rl_learning_rate' => 'rlLearningRate',
            'admission_learning_rate' => 'admissionLearningRate', 'admission_threshold' => 'admissionThreshold',
            'exploration_rate' => 'explorationRate', 'max_object_fraction' => 'maxObjectFraction');
        $ints = array('min_admission_samples' => 'minAdmissionSamples', 'window_size' => 'windowSize',
            'min_history' => 'minHistory', 'metadata_capacity' => 'metadataCapacity');
        foreach ($floats as $k => $prop) {
            if (isset($params[$k])) {
                $this->$prop = (float) $params[$k];
            }
        }
        foreach ($ints as $k => $prop) {
            if (isset($params[$k])) {
                $this->$prop = (int) $params[$k];
            }
        }
        if (isset($params['tier_costs'])) {
            $this->tierCosts = array_map('floatval', (array) $params['tier_costs']);
        }
        // numpy tire une graine au hasard quand seed vaut None
        $seed = isset($params['seed']) && $params['seed'] !== '' ? (int) $params['seed'] : mt_rand();
        $this->rng = new Aicache_CacheusPP_Pcg64($seed);

        $this->weights = array_fill(0, self::NUM_EXPERTS, 1 / self::NUM_EXPERTS);
        $this->history = array(array(), array(), array());
        $this->lr = $this->learningRate;
        $this->theta = array_fill(0, self::NUM_EXPERTS, array_fill(0, self::STATE_DIM, 0.0));
        $this->admissionW = array_fill(0, self::ADMIT_DIM, 0.0);
    }

    // ------------------------------------------------------------------
    // Interface de cache_benchmark
    // ------------------------------------------------------------------

    public function get($key, $size, $category, $missCost = null)
    {
        $this->clock++;
        $this->observeAccess($key);

        if (isset($this->meta[$key])) {
            $entry = $this->meta[$key];
            $entry->freq++;
            $entry->hits++;
            $entry->lastAccess = $this->clock;
            if ($entry->hits === 1) {
                $this->coldEntries--;
            }
            if (!$entry->labeled && $entry->admitFeatures !== null) {
                $this->trainAdmission($entry->admitFeatures, 1.0);
                $entry->labeled = true;
            }
            unset($this->lru[$key]);
            $this->lru[$key] = true;
            $this->touch($key, $entry);
            $this->recordRequest(true);
            return true;
        }

        $this->onGhostMiss($key);
        if (isset($this->rejected[$key])) {
            // une clé refusée revient : l'admettre aurait payé
            $f = $this->rejected[$key];
            unset($this->rejected[$key]);
            $this->trainAdmission($f, 1.0);
        }
        $this->recordRequest(false);
        return false;
    }

    /** @return string[] clés évincées (put() de Python renvoie leur nombre) */
    public function put($key, $size, $category, $missCost = null)
    {
        $evicted = array();
        if (isset($this->cache[$key]) || $size > $this->cacheSize) {
            return $evicted;
        }
        $features = $this->takePendingFeatures($key, $size, $category, $missCost);

        while ($this->currentSize + $size > $this->cacheSize && $this->cache) {
            list($victim, $expert, $state) = $this->selectVictim($size, $category);
            $this->evict($victim);
            $this->addHistory($expert, $victim, $state);
            $this->expertEvictions[$expert]++;
            $evicted[] = (string) $victim;
        }
        $this->insert($key, $size, $category, $missCost, $features);
        return $evicted;
    }

    /** Admission apprise : admet si la probabilité prédite passe le seuil. */
    public function shouldCache($key, $size, $category, $missCost = null)
    {
        if (isset($this->cache[$key])) {
            return true;
        }
        if ($size > $this->cacheSize * $this->maxObjectFraction) {
            return false;
        }
        $features = $this->admissionFeatures($key, $size, $category, $missCost);
        $this->pending = array((string) $key, $features);

        if ($this->currentSize + $size <= $this->cacheSize) {
            return true;
        }
        if ($this->admissionSamples < $this->minAdmissionSamples) {
            return true;
        }
        if ($this->rng->random() < $this->explorationRate) {
            return true;
        }
        if ($this->admissionProbability($features) >= $this->admissionThreshold) {
            return true;
        }
        $this->rememberRejected($key, $features);
        $this->rejections++;
        return false;
    }

    /** Retire une entrée hors décision de l'algorithme (purge, nouvelle taille) : ni historique ni apprentissage. */
    public function drop($key)
    {
        if (isset($this->meta[$key])) {
            $this->meta[$key]->labeled = true;
            $this->evict($key);
        }
    }

    // ------------------------------------------------------------------
    // Éviction : experts, minimisation du regret, gradient de politique
    // ------------------------------------------------------------------

    protected function selectVictim($size, $category)
    {
        $state = $this->evictionState($size, $category);
        $expert = $this->rng->choice($this->policy($state));

        if ($expert === self::LRU) {
            $victim = $this->firstLru();
        } elseif ($expert === self::LFU) {
            $victim = $this->peek($this->lfuHeap, 4);
        } else {
            $victim = $this->peek($this->gdsfHeap, 3);
            if ($victim !== null) {
                $this->gdsfInflation = $this->gdsfHeap[0][0];
            }
        }
        if ($victim === null) {
            list($victim, $expert) = array($this->firstLru(), self::LRU);
        }
        return array($victim, $expert, $state);
    }

    protected function firstLru()
    {
        foreach ($this->lru as $k => $_) {
            return (string) $k;
        }
        return null;
    }

    protected function policy(array $state)
    {
        $logits = array();
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            $logits[$e] = log($this->weights[$e]) + self::dotState($this->theta[$e], $state);
        }
        $max = max($logits);
        $probs = array();
        $sum = 0.0;
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            $probs[$e] = exp($logits[$e] - $max);
            $sum += $probs[$e];
        }
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            $probs[$e] /= $sum;
        }
        return $probs;
    }

    /**
     * Une ligne de theta @ state comme le dgemv d'OpenBLAS (noyau AVX2) qu'utilise numpy :
     * quatre produits sommés deux à deux, puis le cinquième en multiplication-addition fusionnée.
     */
    public static function dotState(array $a, array $x)
    {
        $s = ($a[0] * $x[0] + $a[2] * $x[2]) + ($a[1] * $x[1] + $a[3] * $x[3]);
        return self::fma($a[4], $x[4], $s);
    }

    /** a*b+c arrondi une seule fois (PHP < 8.4 n'a pas fma) : produit et somme exacts de Dekker. */
    public static function fma($a, $b, $c)
    {
        $p = $a * $b;
        $t = 134217729.0 * $a;
        $ah = $t - ($t - $a);
        $al = $a - $ah;
        $t = 134217729.0 * $b;
        $bh = $t - ($t - $b);
        $bl = $b - $bh;
        $pe = (($ah * $bh - $p) + $ah * $bl + $al * $bh) + $al * $bl;
        $s = $p + $c;
        $v = $s - $p;
        $se = ($p - ($s - $v)) + ($c - $v);
        return $s + ($pe + $se);
    }

    protected function evictionState($size, $category)
    {
        $n = count($this->cache);
        $cold = $n ? $this->coldEntries / $n : 0.0;
        $sizeRatio = log1p($size) / log1p($this->cacheSize);
        $share = $this->currentSize
            ? (isset($this->catBytes[$category]) ? $this->catBytes[$category] : 0) / $this->currentSize : 0.0;
        return array(1.0, $this->prevHitRate, $cold, $sizeRatio, $share);
    }

    protected function onGhostMiss($key)
    {
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            if (!isset($this->history[$e][$key])) {
                continue;
            }
            list($evictedAt, $state) = $this->history[$e][$key];
            unset($this->history[$e][$key]);
            // remise de LeCaR : le regret s'estompe avec le temps écoulé depuis l'éviction
            $discount = pow(0.005, 1.0 / max(1, count($this->cache)));
            $regret = pow($discount, (float) ($this->clock - $evictedAt));
            $this->weights[$e] *= exp(-$this->lr * $regret);
            $this->normalizeWeights();
            $this->policyGradient($e, $state, -$regret);
        }
    }

    protected function addHistory($expert, $key, array $state)
    {
        $this->history[$expert][$key] = array($this->clock, $state);
        $limit = max($this->minHistory, count($this->cache));
        while (count($this->history[$expert]) > $limit) {
            reset($this->history[$expert]);
            $old = key($this->history[$expert]);
            $oldState = $this->history[$expert][$old][1];
            unset($this->history[$expert][$old]);
            // la clé évincée n'est pas revenue : bonne éviction
            $this->policyGradient($expert, $oldState, 0.0);
        }
    }

    /** REINFORCE pour une politique softmax linéaire. */
    protected function policyGradient($expert, array $state, $reward)
    {
        $probs = $this->policy($state);
        $advantage = $reward - $this->rewardBaseline;
        $this->rewardBaseline += self::BASELINE_DECAY * ($reward - $this->rewardBaseline);

        $k = $this->rlLearningRate * $advantage;
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            for ($j = 0; $j < self::STATE_DIM; $j++) {
                $g = -($probs[$e] * $state[$j]);
                if ($e === $expert) {
                    $g += $state[$j];
                }
                $t = $this->theta[$e][$j] + $k * $g;
                $this->theta[$e][$j] = $t < -self::THETA_CLIP ? -self::THETA_CLIP : ($t > self::THETA_CLIP ? self::THETA_CLIP : $t);
            }
        }
    }

    protected function normalizeWeights()
    {
        $s = ($this->weights[0] + $this->weights[1]) + $this->weights[2];
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            $this->weights[$e] = max($this->weights[$e] / $s, self::WEIGHT_FLOOR);
        }
        $s = ($this->weights[0] + $this->weights[1]) + $this->weights[2];
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            $this->weights[$e] /= $s;
        }
    }

    protected function recordRequest($hit)
    {
        $this->winHits += $hit ? 1 : 0;
        $this->winRequests++;
        if ($this->winRequests >= $this->windowSize) {
            $this->endWindow();
        }
    }

    /** Ajustement du taux d'apprentissage par montée de colline, comme CACHEUS. */
    protected function endWindow()
    {
        $hitRate = $this->winHits / $this->winRequests;
        if ($hitRate < $this->prevHitRate) {
            $this->lrDirection = -$this->lrDirection;
        }
        if ($hitRate == 0) {
            $this->zeroWindows++;
            if ($this->zeroWindows >= 3) {
                $this->lr = $this->learningRate;
                $this->zeroWindows = 0;
            }
        } else {
            $this->zeroWindows = 0;
        }
        $this->lr = min(self::LR_HI, max(self::LR_LO, $this->lr * (1 + self::LR_STEP * $this->lrDirection)));
        $this->prevHitRate = $hitRate;
        $this->winHits = 0;
        $this->winRequests = 0;
    }

    // ------------------------------------------------------------------
    // Ensemble résident
    // ------------------------------------------------------------------

    protected function insert($key, $size, $category, $missCost, array $features = null)
    {
        $entry = new Aicache_CacheusPP_Entry($size, $category, $this->missCost($category, $missCost),
            isset($this->seen[$key]) ? $this->seen[$key][0] : 1, $this->clock, $features);
        $this->cache[$key] = $size;
        $this->meta[$key] = $entry;
        $this->lru[$key] = true;
        $this->currentSize += $size;
        $this->catBytes[$category] = (isset($this->catBytes[$category]) ? $this->catBytes[$category] : 0) + $size;
        $this->coldEntries++;
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            unset($this->history[$e][$key]);
        }
        unset($this->rejected[$key]);
        $this->touch($key, $entry);
    }

    protected function evict($key)
    {
        $entry = $this->meta[$key];
        unset($this->meta[$key], $this->cache[$key], $this->lru[$key]);
        $this->currentSize -= $entry->size;
        $this->catBytes[$entry->category] -= $entry->size;
        if ($entry->hits === 0) {
            $this->coldEntries--;
        }
        if (!$entry->labeled && $entry->admitFeatures !== null) {
            // admise mais jamais servie : admission perdue
            $this->trainAdmission($entry->admitFeatures, 0.0);
        }
    }

    /** Nouvelles entrées de tas ; les anciennes deviennent périmées par le numéro de version. */
    protected function touch($key, Aicache_CacheusPP_Entry $entry)
    {
        $key = (string) $key;
        $entry->version++;
        self::heapPush($this->lfuHeap, array($entry->freq, $entry->lastAccess, $entry->version, $key));
        $priority = $this->gdsfInflation + $entry->freq * $entry->cost / max(1, $entry->size);
        self::heapPush($this->gdsfHeap, array($priority, $entry->version, $key));
        if (count($this->lfuHeap) > max(4 * count($this->meta) + 1024, 2 * $this->keptAfterCompact)) {
            $this->compactHeaps();
        }
    }

    protected function peek(array &$heap, $width)
    {
        while ($heap) {
            $version = $heap[0][$width - 2];
            $key = $heap[0][$width - 1];
            if (isset($this->meta[$key]) && $this->meta[$key]->version === $version) {
                return $key;
            }
            self::heapPop($heap);
        }
        return null;
    }

    /**
     * Retire les entrées périmées. Sans effet sur les décisions : peek() renvoie toujours la
     * plus petite entrée valide, qu'il reste des périmées ou non. On peut donc compacter plus
     * rarement que Python, ce qu'il faut ici : une clé réinsérée repart à la version 1, ses
     * anciennes entrées redeviennent « valides » et le tas ne redescend plus sous le seuil
     * d'origine, qui compacterait alors à chaque accès (O(n) en C pour Python, trop cher en PHP).
     */
    protected function compactHeaps()
    {
        foreach (array('lfuHeap' => 4, 'gdsfHeap' => 3) as $name => $w) {
            $kept = array();
            foreach ($this->$name as $item) {
                $k = $item[$w - 1];
                if (isset($this->meta[$k]) && $this->meta[$k]->version === $item[$w - 2]) {
                    $kept[] = $item;
                }
            }
            for ($i = (count($kept) >> 1) - 1; $i >= 0; $i--) {
                self::siftDown($kept, $i);
            }
            $this->$name = $kept;
        }
        $this->keptAfterCompact = count($this->lfuHeap);
    }

    protected function missCost($category, $missCost)
    {
        if ($missCost !== null) {
            return (float) $missCost;
        }
        return isset($this->tierCosts[$category]) ? $this->tierCosts[$category] : 1.0;
    }

    // --- tas binaire de tuples, ordre de heapq (comparaison élément par élément) ---------

    protected static function less(array $a, array $b)
    {
        foreach ($a as $i => $x) {
            $y = $b[$i];
            if (is_string($x)) {
                $c = strcmp($x, $y);
                if ($c !== 0) {
                    return $c < 0;
                }
            } elseif ($x != $y) {
                return $x < $y;
            }
        }
        return false;
    }

    protected static function heapPush(array &$h, array $item)
    {
        $i = count($h);
        $h[] = $item;
        while ($i > 0) {
            $p = ($i - 1) >> 1;
            if (!self::less($h[$i], $h[$p])) {
                break;
            }
            list($h[$i], $h[$p]) = array($h[$p], $h[$i]);
            $i = $p;
        }
    }

    protected static function heapPop(array &$h)
    {
        $last = array_pop($h);
        if (!$h) {
            return;
        }
        $h[0] = $last;
        self::siftDown($h, 0);
    }

    protected static function siftDown(array &$h, $i)
    {
        $n = count($h);
        while (true) {
            $l = 2 * $i + 1;
            if ($l >= $n) {
                break;
            }
            $m = ($l + 1 < $n && self::less($h[$l + 1], $h[$l])) ? $l + 1 : $l;
            if (!self::less($h[$m], $h[$i])) {
                break;
            }
            list($h[$i], $h[$m]) = array($h[$m], $h[$i]);
            $i = $m;
        }
    }

    // ------------------------------------------------------------------
    // Modèle d'admission
    // ------------------------------------------------------------------

    public function admissionProbability(array $features)
    {
        $z = 0.0;
        for ($i = 0; $i < self::ADMIT_DIM; $i++) {
            $z += $this->admissionW[$i] * $features[$i];
        }
        return 1.0 / (1.0 + exp(-max(-30.0, min(30.0, $z))));
    }

    protected function admissionFeatures($key, $size, $category, $missCost)
    {
        $freq = isset($this->seen[$key]) ? $this->seen[$key][0] : 0;
        $gap = ($this->lastKey === (string) $key) ? $this->lastGap : null;
        $cost = $this->missCost($category, $missCost);

        $x = array_fill(0, self::ADMIT_DIM, 0.0);
        $x[0] = 1.0;
        $x[1] = log1p($size) / log1p($this->cacheSize);
        $x[2] = min(1.0, log1p($freq) / log1p(1000));
        $x[3] = $gap === null ? 1.0 : min(1.0, log1p($gap) / log1p($this->metadataCapacity));
        $x[4] = $cost / (1.0 + $cost);
        $x[5 + $this->categoryBucket($category)] = 1.0;
        return $x;
    }

    protected function categoryBucket($category)
    {
        if (!isset($this->categoryIndex[$category])) {
            // stable d'une exécution à l'autre ; au-delà, les catégories partagent le dernier seau
            $this->categoryIndex[$category] = min(count($this->categoryIndex), self::NUM_CATEGORY_BUCKETS - 1);
        }
        return $this->categoryIndex[$category];
    }

    protected function takePendingFeatures($key, $size, $category, $missCost)
    {
        $pending = $this->pending;
        $this->pending = null;
        if ($pending !== null && $pending[0] === (string) $key) {
            return $pending[1];
        }
        return $this->admissionFeatures($key, $size, $category, $missCost);
    }

    protected function trainAdmission(array $features, $label)
    {
        $d = $label - $this->admissionProbability($features);
        for ($i = 0; $i < self::ADMIT_DIM; $i++) {
            $this->admissionW[$i] += $this->admissionLearningRate
                * ($d * $features[$i] - self::ADMISSION_L2 * $this->admissionW[$i]);
        }
        $this->admissionSamples++;
    }

    protected function rememberRejected($key, array $features)
    {
        unset($this->rejected[$key]);
        $this->rejected[$key] = $features;
        $limit = max($this->minHistory, count($this->cache));
        while (count($this->rejected) > $limit) {
            reset($this->rejected);
            $old = key($this->rejected);
            $f = $this->rejected[$old];
            unset($this->rejected[$old]);
            // la clé refusée n'est pas revenue : le refus était juste
            $this->trainAdmission($f, 0.0);
        }
    }

    protected function observeAccess($key)
    {
        if (!isset($this->seen[$key])) {
            $this->lastGap = null;
            $this->seen[$key] = array(1, $this->clock);
            if (count($this->seen) > $this->metadataCapacity) {
                reset($this->seen);
                unset($this->seen[key($this->seen)]);
            }
        } else {
            $s = $this->seen[$key];
            unset($this->seen[$key]);
            $this->lastGap = $this->clock - $s[1];
            $this->seen[$key] = array($s[0] + 1, $this->clock);
        }
        $this->lastKey = (string) $key;
    }

    // ------------------------------------------------------------------
    // Diagnostic
    // ------------------------------------------------------------------

    public function stats()
    {
        $w = array();
        foreach (self::$expertNames as $i => $n) {
            $w[$n] = round($this->weights[$i], 4);
        }
        return array(
            'expert_weights' => $w,
            'expert_evictions' => array_combine(self::$expertNames, $this->expertEvictions),
            'learning_rate' => round($this->lr, 4),
            'admission_samples' => $this->admissionSamples,
            'admission_rejections' => $this->rejections,
        );
    }
}
