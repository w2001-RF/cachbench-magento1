<?php
/** Entrée de LIRS : statut LIR ou HIR, résidente ou non. */
class Aicache_Official_LirsEntry
{
    public $oblock;
    public $isLir;
    public $inCache;

    public function __construct($oblock, $isLir = false, $inCache = true)
    {
        $this->oblock = (string) $oblock;
        $this->isLir = $isLir;
        $this->inCache = $inCache;
    }
}
