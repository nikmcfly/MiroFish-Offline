#!/usr/bin/env perl

# Copyright 2024 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# This evaluation script is a modification/correction of the official CNEC 2.0
# evaluation script distributed with the CNEC 2.0 (Czech Named Entity Corpus)
# here: https://ufal.mff.cuni.cz/cnec/cnec2.0.
#
# The modifications made here prevent failure on zero division in case of very
# poor system predictions, which is often the case in the very first epochs of
# training.

# Reads sequence of N named entity recognizers outputs (filenames) and
# evaluates them to the first one.
#
# This script is based on the official CNEC 2.0 compare_ne_ouputs_v3.pl
# evaluation script only with modifications avoiding failure on zero division,
# which the original script handled poorly.
#
# Usage:
# ------
#
# ./compare_ne_outputs.pl gold_filename system_filename_1 [system_filename_2 ... system_filename_N]
#
# Input format:
# -------------
#
# Tabulator separated columns, one line per entity. For each entity, the line is:
#
# <unique entity id>tab<entity class>tab<entity text>
#
# E.g.
#
# token-s12-w1  person  Pepa
# token-s13-w4  country Anglie
#
# Unique entity ids must (obviously) be shared between the gold and system
# output files, e.g. m-rf from PDT from the original file is a good choice. For
# multiword entities, unique entity id is composed of sorted comma separated
# concatenation of the corresponding word ids.
#
# E.g.
#
# token-s12-w1,token-s12-w2     P       Pepa Novak
# token-s13-w1,tokens13-w2      P       Ruzena Novakova
#
# It is possible to give more classifications for one word.
#
# E.g.
#
# token-s12-w1  location  Vltava
# token-s12-w1  person  Vltava
#
# Hierarchical (embedded) entities must be decomposed:
#
# <if Skody<gu Plzen>> =>
#
# id1,id2       if      Skody Plzen
# id2           gu      Plzen
#
# Evaluation rules:
# -----------------
#
# Both span and correct class(es) must guessed correctly for each named entity
# (= each line). When multiple classes exist in the gold data, each is
# considered a separate named entity (= multiple lines). Hierarchical
# (embedded) entities are decomposed into separate entities (=multiple lines)
# which are considered separately.
#
# Author:
# -------
#
# Jana Strakova <strakova@ufal.mff.cuni.cz>
#
# Copyright and licence:
# ----------------------
#
# This module is part of Czech Named Entity Corpus 2.0 release. Please see
# README for licensing info.

use strict;
use warnings;

$#ARGV >= 1 or die "Usage: compare_ne_recognizers.pl gold.filename system_filename_1 [system_filename_2 ... system_filename_N  ]";

our %id2name;

our %CLASSES = (
  'A'  => 1, 'C'  => 1, 'P'  => 1, 'T'  => 1,
  'ah' => 1, 'at' => 1, 'az' => 1,
  'g_' => 1, 'gc' => 1, 'gh' => 1, 'gl' => 1, 'gq' => 1,
  'gr' => 1, 'gs' => 1, 'gt' => 1, 'gu' => 1,
  'i_' => 1, 'ia' => 1, 'ic' => 1, 'if' => 1, 'io' => 1,
  'me' => 1, 'mi' => 1, 'mn' => 1, 'ms' => 1,
  'n_' => 1, 'na' => 1, 'nb' => 1, 'nc' => 1, 'ni' => 1,
  'no' => 1, 'ns' => 1,
  'o_' => 1, 'oa' => 1, 'oe' => 1, 'om' => 1, 'op' => 1,
  'or' => 1,
  'p_' => 1, 'pc' => 1, 'pd' => 1, 'pf' => 1, 'pm' => 1,
  'pp' => 1, 'ps' => 1,
  'td' => 1, 'tf' => 1, 'th' => 1, 'tm' => 1, 'ty' => 1);

sub read_ne($$) {
    my ($filename, $ne_ref) = @_;
    open F,"<$filename" or die "Cannot open file $filename\n";
#    print STDERR "Reading file $filename\n";
    while (<F>) {
        chomp;
        my ($ne, $class, $normalized_name) = split /\t/;
        if (exists $CLASSES{$class}) {
            # add this classification to list of classifications for this word
            $ne_ref->{$ne} = {} if not exists $ne_ref->{$ne};
            $ne_ref->{$ne}->{$class}=1;
            $id2name{$ne} = $normalized_name;
        }
    }
    foreach my $ne (keys %{$ne_ref}) {
      $ne_ref->{$ne} = [keys %{$ne_ref->{$ne}}];
    }
}

sub get_subtypes(@) {
  my @subtypes = map { substr $_, 0, 1 } @_;
  my %seen;
  return grep { !$seen{$_}++ } @subtypes;
}

sub num_of_correct_types($$) {
    my ($gold_ref, $test_ref) = @_;

    my $num = 0;
    foreach my $t (@{$test_ref}) {
        foreach my $g (@{$gold_ref}) {
            $num++ if $t eq $g;
        }
    }
    return $num;
}

sub num_of_correct_suptypes($$) {
    my ($gold_ref, $test_ref) = @_;

    my $num = 0;
    foreach my $t (get_subtypes(@{$test_ref})) {
        foreach my $g (get_subtypes(@{$gold_ref})) {
            $num++ if $t eq $g;
        }
    }
    return $num;
}

sub is_member($$) {
    my ($member, $array_ref) = @_;
    foreach my $a (@{$array_ref}) {
        return 1 if $a eq $member;
    }
    return 0;
}

# read gold data
my %gold;
read_ne($ARGV[0], \%gold);

# read and compare evaluated data
foreach my $i (1..$#ARGV) {

    # read
    my %entities;
    read_ne($ARGV[$i], \%entities);

    # compare

    # all entities
    my $correct = 0;                    # correct, that is number of nes in gold
    my $correct_subtype = 0;            # correct, that is number of subtypes in gold
    my $correct_span = 0;               # correct, that is number of spans in gold
    my $retrieved = 0;                  # retrieved, that is number of nes in test
    my $retrieved_subtype = 0;          # retrieved, that is number of subtypes in test
    my $retrieved_span = 0;             # retrieved, that is number of spans in test
    my $correct_retrieved = 0;          # correct retrieved type
    my $correct_retrieved_suptype = 0;  # correct retrieved supertype
    my $correct_retrieved_span = 0;     # correct retrieved span

    # oneword entities (same numbers restricted for oneword entities)
    my $correct_oneword = 0;
    my $correct_oneword_subtype = 0;
    my $correct_oneword_span = 0;
    my $retrieved_oneword = 0;
    my $retrieved_oneword_subtype = 0;
    my $retrieved_oneword_span = 0;
    my $correct_retrieved_oneword = 0;
    my $correct_retrieved_suptype_oneword = 0;
    my $correct_retrieved_span_oneword = 0;

    # twoword entities (same numbers restricted for twoword entities)
    my $correct_twoword = 0;
    my $correct_twoword_subtype = 0;
    my $correct_twoword_span = 0;
    my $retrieved_twoword = 0;
    my $retrieved_twoword_subtype = 0;
    my $retrieved_twoword_span = 0;
    my $correct_retrieved_twoword = 0;
    my $correct_retrieved_suptype_twoword = 0;
    my $correct_retrieved_span_twoword = 0;

    # count number of gold entities -- sum lists of classifications for each word
    foreach my $gold_ne (keys %gold) {
        $correct += @{$gold{$gold_ne}};
        $correct_subtype += get_subtypes(@{$gold{$gold_ne}});
        $correct_span++;
        if ($gold_ne !~ /,/) {
            $correct_oneword += @{$gold{$gold_ne}};
            $correct_oneword_subtype += get_subtypes(@{$gold{$gold_ne}});
            $correct_oneword_span++;
        }
        if ($gold_ne =~ /^[^,]+,[^,]+$/) {
            $correct_twoword += @{$gold{$gold_ne}};
            $correct_twoword_subtype += get_subtypes(@{$gold{$gold_ne}});
            $correct_twoword_span++;
        }
    }

    # count number of retrieved entities -- sum lists of classifications for each word
    foreach my $ne (keys %entities) {
        $retrieved += @{$entities{$ne}};
        $retrieved_subtype += get_subtypes(@{$entities{$ne}});
        $retrieved_span++;
        if ($ne !~ /,/) {
            $retrieved_oneword += @{$entities{$ne}};
            $retrieved_oneword_subtype += get_subtypes(@{$entities{$ne}});
            $retrieved_oneword_span++;
        }
        if ($ne =~ /^[^,]+,[^,]+$/) {
            $retrieved_twoword += @{$entities{$ne}};
            $retrieved_twoword_subtype += get_subtypes(@{$entities{$ne}});
            $retrieved_twoword_span++;
        }
    }

    # count number of correct retrieved entities
    foreach my $ne (keys %entities) {
        # all entities
        $correct_retrieved += num_of_correct_types($gold{$ne},$entities{$ne}) if exists $gold{$ne};
        $correct_retrieved_suptype += num_of_correct_suptypes($gold{$ne},$entities{$ne}) if exists $gold{$ne};
        $correct_retrieved_span++ if exists $gold{$ne};
        # oneword
        if ($ne !~ /,/) {
            $correct_retrieved_oneword += num_of_correct_types($gold{$ne},$entities{$ne}) if exists $gold{$ne};
            $correct_retrieved_suptype_oneword += num_of_correct_suptypes($gold{$ne},$entities{$ne}) if exists $gold{$ne};
            $correct_retrieved_span_oneword++ if exists $gold{$ne};
        }
        # twoword
        if ($ne =~ /^[^,]+,[^,]+$/) {
            $correct_retrieved_twoword += num_of_correct_types($gold{$ne},$entities{$ne}) if exists $gold{$ne};
            $correct_retrieved_suptype_twoword += num_of_correct_suptypes($gold{$ne},$entities{$ne}) if exists $gold{$ne};
            $correct_retrieved_span_twoword++ if exists $gold{$ne};
        }
    }

    # type (typ pojmenovane entity)

    my $recall = ($correct > 0) ? $correct_retrieved / $correct : 0;
    my $precision = ($retrieved > 0) ? $correct_retrieved / $retrieved : 0;
    my $f_measure = ($recall + $precision > 0) ? 2 * $recall * $precision / ($recall + $precision) : 0;

    my ($recall_twoword, $precision_twoword, $f_measure_twoword) = (0, 1, 0);
    if ($correct_retrieved_twoword > 0 and $retrieved_twoword > 0) {
      $recall_twoword = $correct_retrieved_twoword / $correct_twoword;
      $precision_twoword = $correct_retrieved_twoword / $retrieved_twoword;
      $f_measure_twoword = (2 * $recall_twoword * $precision_twoword) / ($recall_twoword + $precision_twoword);
    }

    my $recall_oneword = ($correct_oneword > 0) ? $correct_retrieved_oneword / $correct_oneword : 0;
    my $precision_oneword = ($retrieved_oneword > 0) ? $correct_retrieved_oneword / $retrieved_oneword : 0;
    my $f_measure_oneword = ($recall_oneword + $precision_oneword > 0) ? 2 * $recall_oneword * $precision_oneword / ($recall_oneword + $precision_oneword) : 0;

    # suptype (nadtyp pojmenovane entity)

    my $recall_suptype = ($correct_subtype > 0) ? $correct_retrieved_suptype / $correct_subtype : 0;
    my $precision_suptype = ($retrieved_subtype > 0) ? $correct_retrieved_suptype / $retrieved_subtype : 0;
    my $f_measure_suptype = ($recall_suptype + $precision_suptype) ? 2 * $recall_suptype * $precision_suptype / ($recall_suptype + $precision_suptype) : 0;

    my ($recall_suptype_twoword, $precision_suptype_twoword, $f_measure_suptype_twoword) = (0, 1, 0);
    if ($correct_retrieved_suptype_twoword > 0 and $retrieved_twoword > 0) {
      $recall_suptype_twoword = $correct_retrieved_suptype_twoword / $correct_twoword_subtype;
      $precision_suptype_twoword = $correct_retrieved_suptype_twoword / $retrieved_twoword_subtype;
      $f_measure_suptype_twoword = (2 * $recall_suptype_twoword * $precision_suptype_twoword) / ($recall_suptype_twoword + $precision_suptype_twoword);
    }

    my $recall_suptype_oneword = ($correct_oneword_subtype > 0) ? $correct_retrieved_suptype_oneword / $correct_oneword_subtype : 0;
    my $precision_suptype_oneword = ($retrieved_oneword_subtype > 0) ? $correct_retrieved_suptype_oneword / $retrieved_oneword_subtype : 0;
    my $f_measure_suptype_oneword = ($recall_suptype_oneword + $precision_suptype_oneword > 0) ? (2 * $recall_suptype_oneword * $precision_suptype_oneword) / ( $recall_suptype_oneword + $precision_suptype_oneword) : 0;

    # entity span recognition (rozsah pojmenovane entity)

    my $recall_span = ($correct_span) ? $correct_retrieved_span / $correct_span : 0;
    my $precision_span = ($retrieved_span) ? $correct_retrieved_span / $retrieved_span : 0;
    my $f_measure_span = ($recall_span + $precision_span > 0) ? (2 * $recall_span * $precision_span) / ($recall_span + $precision_span) : 0;

    my $recall_span_oneword = ($correct_oneword_span > 0) ? $correct_retrieved_span_oneword / $correct_oneword_span : 0;
    my $precision_span_oneword = ($retrieved_oneword_span > 0) ? $correct_retrieved_span_oneword / $retrieved_oneword_span : 0;
    my $f_measure_span_oneword = ($recall_span_oneword + $precision_span_oneword) ? (2 * $recall_span_oneword * $precision_span_oneword) / ($recall_span_oneword + $precision_span_oneword) : 0;

    my ($recall_span_twoword, $precision_span_twoword, $f_measure_span_twoword) = (0, 1, 0);
    if ($correct_retrieved_span_twoword > 0 and $retrieved_twoword_span > 0) {
      $recall_span_twoword = $correct_retrieved_span_twoword / $correct_twoword_span;
      $precision_span_twoword = $correct_retrieved_span_twoword / $retrieved_twoword_span;
      $f_measure_span_twoword = (2 * $recall_span_twoword * $precision_span_twoword) / ($recall_span_twoword + $precision_span_twoword);
    }

    # print
    print "-------------\n";
    print "$ARGV[$i]\n";
    print "Gold entities: $correct (all), $correct_oneword (oneword), $correct_twoword (twoword)\n";
    print "Retrieved entities: $retrieved (all), $retrieved_oneword (oneword), $retrieved_twoword (twoword)\n";

    print "\n";
    print  "All entities (p/r/f)           | Oneword (p/r/f)       | Twoword (p/r/f)\n";

    printf "Type:    %2.2f / %2.2f / %2.2f | %2.2f / %2.2f / %2.2f | %2.2f / %2.2f / %2.2f\n",
            $precision * 100, $recall * 100, $f_measure * 100,
            $precision_oneword * 100, $recall_oneword * 100, $f_measure_oneword * 100,
            $precision_twoword * 100, $recall_twoword * 100, $f_measure_twoword * 100;
    printf "Suptype: %2.2f / %2.2f / %2.2f | %2.2f / %2.2f / %2.2f | %2.2f / %2.2f / %2.2f\n",
            $precision_suptype * 100, $recall_suptype * 100, $f_measure_suptype * 100,
            $precision_suptype_oneword * 100, $recall_suptype_oneword * 100, $f_measure_suptype_oneword * 100,
            $precision_suptype_twoword * 100, $recall_suptype_twoword * 100, $f_measure_suptype_twoword * 100;
    printf "Span:    %2.2f / %2.2f / %2.2f | %2.2f / %2.2f / %2.2f | %2.2f / %2.2f / %2.2f\n",
            $precision_span * 100, $recall_span * 100, $f_measure_span * 100,
            $precision_span_oneword * 100, $recall_span_oneword * 100, $f_measure_span_oneword * 100,
            $precision_span_twoword * 100, $recall_span_twoword * 100, $f_measure_span_twoword * 100;

    # create confusion table
    our %conf;
    foreach my $c1 (keys %CLASSES, 'x') {
        $conf{$c1} = ();
        foreach my $c2 (keys %CLASSES, 'x') {
            $conf{$c1}{$c2} = 0;
        }
    }

    foreach my $g (keys %gold) {
        if (not exists $entities{$g}) {             # ne not recognized at all
            map { $conf{$_}{'x'}++ } @{$gold{$g}};
        }
        else {
            my @gold_only;
            my @test_only;
            foreach my $c (@{$gold{$g}}) {
                if (not is_member($c, $entities{$g})) {
                    push @gold_only, $c;
                }
                else {
                    $conf{$c}{$c}++;
                }
            }
            foreach my $c (@{$entities{$g}}) {
                if (not is_member($c, $gold{$g})) {
                    push @test_only, $c;
                }
            }
            foreach my $g_only (@gold_only) {
                foreach my $t_only (@test_only) {
                    $conf{$g_only}{$t_only}++;
                }
            }
        }

    }

    foreach my $ne (keys %entities) {
        if (not exists $gold{$ne}) {
            map { $conf{'x'}{$_}++ } @{$entities{$ne}};
        }
    }

    # print confusion conf
    open CONF,">confusion.txt" or die "Cannot open file confusion.txt for writing\n";
    foreach my $c1 (keys %conf) {
        foreach my $c2 (keys %conf) {
            next if $c1 eq $c2;
            print CONF "$c1 $c2 $conf{$c1}{$c2}\n" if $conf{$c1}{$c2};
        }
    }
    close CONF;

    # entities which are in gold but not marked as entities by test
    open NOTREC,">false_negatives.txt" or die "Cannot open file false_negatives.txt for writing\n";
    foreach my $g (keys %gold) {
        foreach my $c (@{$gold{$g}}) {
            if (not exists $entities{$g}) {
                print NOTREC "$id2name{$g} $c\n";
            }
        }
    }
    close NOTREC;

    # entities which are marked by test as entities but are not in gold
    open INC,">false_positives.txt" or die "Cannot open file false_positives.txt for writing\n";
    foreach my $ne (keys %entities) {
        foreach my $c (@{$entities{$ne}}) {
            if (not exists $gold{$ne}) {
                print INC "$id2name{$ne} $c\n";
            }
        }
    }
    close INC;
}
