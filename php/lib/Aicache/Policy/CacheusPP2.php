<?php
/** CACHEUS++ v2, comme cachebench.policies.cacheus_pp2 : même adaptateur que CACHEUS++. */
class Aicache_Policy_CacheusPP2 extends Aicache_Policy_CacheusPP
{
    public function __construct($capacity, array $params = array())
    {
        if ($capacity <= 0) {
            throw new InvalidArgumentException('la capacité doit être positive');
        }
        $this->capacity = (int) $capacity;
        $this->alg = new Aicache_CacheusPP_AlgorithmV2($this->capacity, $params);
    }
}
