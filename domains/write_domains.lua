-- Maps a semantic target resource or validated spec kind to its guarded write domain.
local M={}
local modules={stratagem='hd2runtime/domains/stratagem_writes',
    armor_perk='hd2runtime/domains/armor_perk_writes',
    mission='hd2runtime/domains/mission_writes',
    melee='hd2runtime/domains/melee_writes',
    entity='hd2runtime/domains/entity_writes',weapon='hd2runtime/domains/player_weapon_writes',
    attachment='hd2runtime/domains/attachment_writes',booster='hd2runtime/domains/booster_writes',
    pod='hd2runtime/domains/pod_payload_writes',throwable='hd2runtime/domains/throwable_writes',
    enemy='hd2runtime/domains/enemy_writes',output='hd2runtime/domains/output_writes',
    explosion='hd2runtime/domains/explosion_writes',helldiver='hd2runtime/domains/helldiver_writes',
    armor_kit='hd2runtime/domains/armor_stats_writes',status_effect='hd2runtime/domains/status_effect_writes',
    beam_conversion='hd2runtime/domains/beam_conversion_writes',enemy_director='hd2runtime/domains/enemy_director_writes'}
local by_resource={stratagem='stratagem',vehicle='entity',backpack='entity',weapon_attachment='attachment',
    armor_perk='armor_perk',
    mission='mission',
    melee='melee',
    player_weapon='weapon',support_weapon='weapon',vehicle_weapon='weapon',booster='booster',pod_rack='pod',
    throwable='throwable',enemy='enemy',attack_output='output',explosion='explosion',helldiver='helldiver',
    armor_kit='armor_kit',armor_class='armor_kit',armor_damage_curve='armor_kit',status_effect='status_effect',
    beam_conversion='beam_conversion',enemy_director='enemy_director'}
function M.typed_resource(resource)return by_resource[resource]~=nil end
function M.typed_kind(kind)
    if kind=='armor_perk'then return true end
    if kind=='mission'then return true end
    if kind=='melee'then return true end
    return kind=='stratagem'or kind=='entity'or kind=='attachment'or kind=='booster'or kind=='pod'
        or kind=='throwable'or kind=='player_weapon'or kind=='support_weapon'or kind=='vehicle_weapon'
        or kind=='enemy'or kind=='attack_output'or kind=='explosion'or kind=='helldiver'or kind=='armor_kit'
        or kind=='status_effect'or kind=='beam_conversion'or kind=='enemy_director'
end
function M.key_for_kind(kind)
    if kind=='armor_perk'then return kind end
    if kind=='mission'then return kind end
    if kind=='melee'then return kind end
    if kind=='enemy_director'then return kind end
    if kind=='stratagem'or kind=='entity'or kind=='attachment'or kind=='booster'or kind=='pod'
        or kind=='throwable'or kind=='enemy'or kind=='explosion'or kind=='helldiver'or kind=='armor_kit'
        or kind=='status_effect'or kind=='beam_conversion'then
        return kind
    end
    if kind=='attack_output'then return 'output'end
    return 'weapon'
end
function M.for_resource(resource)
    return require(modules[assert(by_resource[resource],'unsupported authoring target: '..tostring(resource))])
end
function M.for_kind(kind)return require(modules[M.key_for_kind(kind)])end
return M
