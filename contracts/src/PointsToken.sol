// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title PointsToken
/// @notice Reward points. 1 unit = 1 whole point (0 decimals), always worth $0.01
///         of USDC held by the RewardsVault. Only the vault can mint or burn, and
///         points cannot be transferred between customers.
contract PointsToken is ERC20, Ownable {
    address public vault;

    error VaultAlreadySet();
    error ZeroAddress();
    error OnlyVault();
    error TransfersDisabled();

    event VaultSet(address indexed vault);

    constructor(address initialOwner) ERC20("Reward Points", "PTS") Ownable(initialOwner) {}

    modifier onlyVault() {
        if (msg.sender != vault) revert OnlyVault();
        _;
    }

    function decimals() public pure override returns (uint8) {
        return 0;
    }

    /// @notice Links the token to its vault. Can be called once, by the owner.
    function setVault(address vault_) external onlyOwner {
        if (vault != address(0)) revert VaultAlreadySet();
        if (vault_ == address(0)) revert ZeroAddress();
        vault = vault_;
        emit VaultSet(vault_);
    }

    function mint(address to, uint256 points) external onlyVault {
        _mint(to, points);
    }

    function burn(address from, uint256 points) external onlyVault {
        _burn(from, points);
    }

    /// @dev Allow only mints (from = 0) and burns (to = 0).
    function _update(address from, address to, uint256 value) internal override {
        if (from != address(0) && to != address(0)) revert TransfersDisabled();
        super._update(from, to, value);
    }
}
