<?php
/**
 * Contrat d'une politique de cache : même interface que cachebench.policies.CachePolicy.
 */
interface Aicache_Policy_Interface
{
    /** Traite une requête cachable. Renvoie true si c'est un hit. */
    public function access(Aicache_Request $req);

    /** Retire les entrées portant un de ces tags. Renvoie le nombre retiré. */
    public function invalidate(array $tags);

    public function usedBytes();

    public function contains($key);

    public function getCapacity();

    public function getEvictions();

    /**
     * Clés évincées depuis le dernier appel (le backend Magento les supprime du stockage réel).
     * @return string[]
     */
    public function popEvicted();
}
