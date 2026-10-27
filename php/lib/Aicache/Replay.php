<?php
/**
 * Rejoue une trace avec les mêmes règles que cachebench.engine.simulate :
 * échauffement exclu, pages non cachables comptées à leur coût, purges eager ou lazy,
 * tailles en octets ou unitaires.
 */
class Aicache_Replay
{
    public $warmup = 0.1;
    public $hitCostMs = 0.5;
    public $sizes = 'bytes';
    public $invalidation = 'eager';

    /**
     * @param Aicache_Request[] $trace
     * @param array|null $hits si fourni, reçoit 1/0 pour chaque requête jouée (échauffement compris)
     */
    public function run(Aicache_Policy_Interface $policy, array $trace, &$hits = null)
    {
        $nGets = 0;
        foreach ($trace as $r) {
            if ($r->op === Aicache_Request::GET) {
                $nGets++;
            }
        }
        $warmUntil = (int) ($nGets * $this->warmup);
        $lazy = $this->invalidation === 'lazy';
        $byTag = array();
        $stale = array();
        $lat = array();
        $seen = $measured = $nHits = 0;
        $bytesHit = $bytesTotal = 0;
        $overhead = 0.0;
        $hits = array();

        foreach ($trace as $r) {
            if ($r->op === Aicache_Request::PURGE) {
                if ($lazy) {
                    foreach ($r->tags as $t) {
                        if (isset($byTag[$t])) {
                            $stale += $byTag[$t];
                            unset($byTag[$t]);
                        }
                    }
                } else {
                    $policy->invalidate($r->tags);
                }
                continue;
            }
            if ($this->sizes === 'unit' && $r->size !== 1) {
                $r = $r->withUnitSize();
            }
            $seen++;
            $measuring = $seen > $warmUntil;
            if (!$r->cacheable) {
                if ($measuring) {
                    $lat[] = $r->costMs;
                }
                continue;
            }
            if (property_exists($policy, 'measuring')) {
                $policy->measuring = $measuring;
            }
            $t0 = microtime(true);
            $hit = $policy->access($r);
            $dt = microtime(true) - $t0;
            if ($lazy) {
                if (isset($stale[$r->key])) {
                    $hit = false;
                    unset($stale[$r->key]);
                }
                foreach ($r->tags as $t) {
                    $byTag[$t][$r->key] = true;
                }
            }
            if ($policy->usedBytes() > $policy->getCapacity()) {
                throw new LogicException('capacité dépassée');
            }
            $policy->popEvicted();
            $hits[] = $hit ? 1 : 0;
            if (!$measuring) {
                continue;
            }
            $measured++;
            $overhead += $dt;
            $bytesTotal += $r->size;
            if ($hit) {
                $nHits++;
                $bytesHit += $r->size;
                $lat[] = $this->hitCostMs;
            } else {
                $lat[] = $r->costMs;
            }
        }
        sort($lat);
        $out = array(
            'requests' => $measured,
            'hit_rate' => $measured ? $nHits / $measured : 0.0,
            'byte_hit_rate' => $bytesTotal ? $bytesHit / $bytesTotal : 0.0,
            'latency_mean_ms' => $lat ? array_sum($lat) / count($lat) : 0.0,
            'latency_p95_ms' => self::percentile($lat, 95),
            'overhead_us' => $measured ? $overhead / $measured * 1e6 : 0.0,
            'evictions' => $policy->getEvictions(),
        );
        if (isset($policy->approxHits)) {
            $out['approx_hit_rate'] = $measured ? $policy->approxHits / $measured : 0.0;
            $out['false_hit_rate'] = $measured ? $policy->falseHits / $measured : 0.0;
        }
        return $out;
    }

    /** Percentile avec interpolation linéaire, comme numpy.percentile. */
    public static function percentile(array $sorted, $p)
    {
        $n = count($sorted);
        if (!$n) {
            return 0.0;
        }
        $pos = ($n - 1) * $p / 100;
        $lo = (int) floor($pos);
        $hi = min($n - 1, $lo + 1);
        return $sorted[$lo] + ($sorted[$hi] - $sorted[$lo]) * ($pos - $lo);
    }
}
