<?php
class Aicache_Policy_Fifo extends Aicache_Policy_Lru
{
    protected function onHit($key, Aicache_Request $req)
    {
    }
}
