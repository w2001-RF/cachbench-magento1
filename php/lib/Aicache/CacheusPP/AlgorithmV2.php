<?php
/**
 * Portage PHP de CACHEUS++ v2 (cachebench/policies/cacheus_pp2.py), mêmes décisions que Python.
 *
 * Paramètres et valeurs par défaut de la version Python : fix_versions, feedback (regret ou
 * counterfactual), history_factor, selection (sample ou argmax), freq_window, admission
 * (logistic ou none), rl, max_object_fraction. L'admission tinylfu de Python, moins bonne, n'est
 * pas portée.
 */
class Aicache_CacheusPP_AlgorithmV2 extends Aicache_CacheusPP_Algorithm
{
    public $fixVersions = true;
    public $feedback = 'counterfactual';
    public $historyFactor = 4.0;
    public $selection = 'sample';
    public $freqWindow = 50.0;
    public $admission = 'none';
    public $rl = true;

    protected $versionClock = 0;
    protected $freq = array();       // clé -> compteur d'accès vieilli
    protected $freqOps = 0;

    public function __construct($cacheSize, array $params = array())
    {
        if (!isset($params['max_object_fraction'])) {
            $params['max_object_fraction'] = 0.5;
        }
        parent::__construct($cacheSize, $params);
        foreach (array('fix_versions' => 'fixVersions', 'rl' => 'rl') as $k => $prop) {
            if (isset($params[$k])) {
                $this->$prop = self::bool($params[$k]);
            }
        }
        foreach (array('history_factor' => 'historyFactor', 'freq_window' => 'freqWindow') as $k => $prop) {
            if (isset($params[$k])) {
                $this->$prop = (float) $params[$k];
            }
        }
        $choices = array('feedback' => array('regret', 'counterfactual'), 'selection' => array('sample', 'argmax'),
            'admission' => array('logistic', 'none'));
        foreach ($choices as $k => $allowed) {
            if (isset($params[$k])) {
                if (!in_array($params[$k], $allowed, true)) {
                    throw new InvalidArgumentException("$k inconnu : {$params[$k]} (" . implode(', ', $allowed) . ')');
                }
                $this->$k = $params[$k];
            }
        }
    }

    protected static function bool($v)
    {
        return is_bool($v) ? $v : in_array(strtolower(trim((string) $v)), array('1', 'true', 'yes', 'on'), true);
    }

    // ------------------------------------------------------------------
    // Interface de cache_benchmark
    // ------------------------------------------------------------------

    public function get($key, $size, $category, $missCost = null)
    {
        $hit = parent::get($key, $size, $category, $missCost);   // sur un miss, appelle onGhostMiss
        if ($hit && $this->feedback === 'counterfactual') {
            // candidat resté dans le cache et redemandé : son expert l'aurait évincé
            $this->onGhostMiss($key);
        }
        return $hit;
    }

    public function shouldCache($key, $size, $category, $missCost = null)
    {
        if ($this->admission === 'logistic') {
            return parent::shouldCache($key, $size, $category, $missCost);
        }
        if (isset($this->cache[$key])) {
            return true;
        }
        return $size <= $this->cacheSize * $this->maxObjectFraction;
    }

    public function put($key, $size, $category, $missCost = null)
    {
        $evicted = array();
        if (isset($this->cache[$key]) || $size > $this->cacheSize) {
            return $evicted;
        }
        $features = $this->admission === 'logistic' ? $this->takePendingFeatures($key, $size, $category, $missCost) : null;

        while ($this->currentSize + $size > $this->cacheSize && $this->cache) {
            list($victim, $expert, $state, $candidates) = $this->choose($size, $category);
            if ($expert === self::GDSF) {
                $this->gdsfInflation = $this->gdsfHeap[0][0];
            }
            $this->evict($victim);
            if ($this->feedback === 'counterfactual') {
                foreach ($candidates as $e => $c) {
                    if ($c !== null) {
                        $this->addHistory($e, $c, $state);
                    }
                }
            } else {
                $this->addHistory($expert, $victim, $state);
            }
            $this->expertEvictions[$expert]++;
            $evicted[] = (string) $victim;
        }
        $this->insert($key, $size, $category, $missCost, $features);
        return $evicted;
    }

    public function drop($key)
    {
        parent::drop($key);
        // retirée de l'extérieur (purge) : ses fantômes ne doivent punir personne
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            unset($this->history[$e][$key]);
        }
    }

    // ------------------------------------------------------------------
    // Choix de la victime
    // ------------------------------------------------------------------

    /** [victime, expert, état, candidats des trois experts], sans rien évincer. */
    protected function choose($size, $category)
    {
        $state = $this->evictionState($size, $category);
        $probs = $this->policy($state);
        if ($this->selection === 'argmax') {
            $expert = 0;
            for ($e = 1; $e < self::NUM_EXPERTS; $e++) {
                if ($probs[$e] > $probs[$expert]) {
                    $expert = $e;
                }
            }
        } else {
            $expert = $this->rng->choice($probs);
        }
        if ($this->feedback !== 'regret') {
            $candidates = array($this->firstLru(), $this->peek($this->lfuHeap, 4), $this->peek($this->gdsfHeap, 3));
        } else {
            // seul le tas de l'expert tiré est lu, comme dans l'original
            $candidates = array(null, null, null);
            if ($expert === self::LRU) {
                $candidates[$expert] = $this->firstLru();
            } elseif ($expert === self::LFU) {
                $candidates[$expert] = $this->peek($this->lfuHeap, 4);
            } else {
                $candidates[$expert] = $this->peek($this->gdsfHeap, 3);
            }
        }
        $victim = $candidates[$expert];
        if ($victim === null) {
            list($victim, $expert) = array($this->firstLru(), self::LRU);
        }
        return array($victim, $expert, $state, $candidates);
    }

    protected function historyLimit()
    {
        return max($this->minHistory, (int) ($this->historyFactor * count($this->cache)));
    }

    protected function addHistory($expert, $key, array $state)
    {
        unset($this->history[$expert][$key]);
        $this->history[$expert][$key] = array($this->clock, $state);
        $limit = $this->historyLimit();
        while (count($this->history[$expert]) > $limit) {
            reset($this->history[$expert]);
            $old = key($this->history[$expert]);
            $oldState = $this->history[$expert][$old][1];
            unset($this->history[$expert][$old]);
            $this->policyGradient($expert, $oldState, 0.0);
        }
    }

    protected function onGhostMiss($key)
    {
        for ($e = 0; $e < self::NUM_EXPERTS; $e++) {
            if (!isset($this->history[$e][$key])) {
                continue;
            }
            list($evictedAt, $state) = $this->history[$e][$key];
            unset($this->history[$e][$key]);
            // remise de LeCaR étalée sur la longueur des fantômes
            $horizon = max(1.0, $this->historyFactor * count($this->cache));
            $discount = pow(0.005, 1.0 / $horizon);
            $regret = pow($discount, (float) ($this->clock - $evictedAt));
            $this->weights[$e] *= exp(-$this->lr * $regret);
            $this->normalizeWeights();
            $this->policyGradient($e, $state, -$regret);
        }
    }

    protected function policyGradient($expert, array $state, $reward)
    {
        if ($this->rl) {
            parent::policyGradient($expert, $state, $reward);
        }
    }

    // ------------------------------------------------------------------
    // Fréquences vieillies et tas
    // ------------------------------------------------------------------

    protected function observeAccess($key)
    {
        parent::observeAccess($key);
        if ($this->freqWindow <= 0) {
            return;
        }
        $this->freq[$key] = (isset($this->freq[$key]) ? $this->freq[$key] : 0) + 1;
        $this->freqOps++;
        if ($this->freqOps >= $this->freqWindow * max($this->minHistory, count($this->cache))) {
            $this->age();
        }
    }

    /** Divise les compteurs par deux et reconstruit le tas LFU, dont les priorités ont changé. */
    protected function age()
    {
        $this->freqOps = 0;
        $halved = array();
        foreach ($this->freq as $k => $c) {
            if ($c > 1) {
                $halved[$k] = $c >> 1;
            }
        }
        $this->freq = $halved;
        $heap = array();
        foreach ($this->meta as $k => $entry) {
            $entry->freq = $this->frequency($k);
            $heap[] = array($entry->freq, $entry->lastAccess, $entry->version, (string) $k);
        }
        for ($i = (count($heap) >> 1) - 1; $i >= 0; $i--) {
            self::siftDown($heap, $i);
        }
        $this->lfuHeap = $heap;
    }

    protected function frequency($key)
    {
        if ($this->freqWindow > 0) {
            return isset($this->freq[$key]) ? $this->freq[$key] : 0;
        }
        return isset($this->seen[$key]) ? $this->seen[$key][0] : 0;
    }

    protected function touch($key, Aicache_CacheusPP_Entry $entry)
    {
        $key = (string) $key;
        if ($this->freqWindow > 0) {
            $entry->freq = $this->frequency($key);
        }
        if ($this->fixVersions) {
            $entry->version = ++$this->versionClock;
        } else {
            $entry->version++;
        }
        self::heapPush($this->lfuHeap, array($entry->freq, $entry->lastAccess, $entry->version, $key));
        $priority = $this->gdsfInflation + $entry->freq * $entry->cost / max(1, $entry->size);
        self::heapPush($this->gdsfHeap, array($priority, $entry->version, $key));
        if (count($this->lfuHeap) > max(4 * count($this->meta) + 1024, 2 * $this->keptAfterCompact)) {
            $this->compactHeaps();
        }
    }

    public function stats()
    {
        $s = parent::stats();
        $s['config'] = array('fix_versions' => $this->fixVersions, 'feedback' => $this->feedback,
            'history_factor' => $this->historyFactor, 'selection' => $this->selection,
            'freq_window' => $this->freqWindow, 'admission' => $this->admission, 'rl' => $this->rl,
            'max_object_fraction' => $this->maxObjectFraction);
        return $s;
    }
}
